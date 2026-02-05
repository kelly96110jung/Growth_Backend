import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Demo',
      theme: ThemeData(
        colorScheme: .fromSeed(seedColor: Colors.green),
      ),
      debugShowCheckedModeBanner: false,
      home: const MyHomePage(title:'MedExplain'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});
  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  final AudioRecorder _recorder = AudioRecorder();

  bool _isListening = false;

  // 기존 "입력된 텍스트" UI를 그대로 쓰되, A 단계에서는 상태/결과 표시로 사용
  String _recognizedText = "버튼을 누르고 녹음을 시작해보세요.";

  DateTime? _recordingStartedAt;
  String? _lastSavedPath;

  @override
  void dispose() {
    _recorder.dispose();
    super.dispose();
  }

  Future<String> _buildOutputPath() async {
    final dir = await getApplicationDocumentsDirectory();
    final fileName =
        "medex_${DateTime.now().millisecondsSinceEpoch}.wav";
    return "${dir.path}/$fileName";
  }

  Future<void> _toggleListening() async {
    if (!_isListening) {
      // 1) 권한 체크
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        setState(() {
          _recognizedText = "마이크 권한이 필요합니다. 설정에서 권한을 허용해주세요.";
        });
        return;
      }
      //======START======
      final outPath = await _buildOutputPath();

      await _recorder.start(
        const RecordConfig(
          encoder: AudioEncoder.wav,
          sampleRate: 16000,
          numChannels: 1,
        ),
        path: outPath,
      );

      setState(() {
        _isListening = true;
        _recordingStartedAt = DateTime.now();
        _lastSavedPath = outPath;
        _recognizedText = "녹음 중...\n$outPath";
      });
    }
    else {
      // ===== STOP =====
      final path = await _recorder.stop();
      final startedAt = _recordingStartedAt;

      final durationMs = startedAt == null
          ? null
          : DateTime.now().difference(startedAt).inMilliseconds;

      if (path == null) {
        setState(() {
          _isListening = false;
          _recognizedText = "녹음 종료 실패 (path == null)";
        });
        return;
      }
      final file = File(path);
      final exists = await file.exists();
      final sizeBytes = exists ? await file.length() : 0;

      setState(() {
        _isListening = false;
        _recognizedText = [
          "녹음 완료",
          "경로: $path",
          if (durationMs != null) "길이(ms): $durationMs",
          "파일 존재: $exists",
          "파일 크기(bytes): $sizeBytes",
          "샘플레이트: 16000Hz",
        ].join("\n");
      });
      debugPrint("RECORD DONE path=$path durationMs=$durationMs size=$sizeBytes");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _toggleListening,
        icon: Icon(_isListening ? Icons.stop : Icons.mic),
        label: Text(_isListening ? "녹음 종료" : "녹음 시작"),
        backgroundColor: _isListening ? Colors.red : Colors.green,
      ),
      floatingActionButtonLocation: FloatingActionButtonLocation.centerFloat,
      body: Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              "의사 설명 텍스트",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: SingleChildScrollView(
                  child: Text(
                    _recognizedText.isEmpty ? "대기 중..." : _recognizedText,
                    style: const TextStyle(fontSize: 16),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
