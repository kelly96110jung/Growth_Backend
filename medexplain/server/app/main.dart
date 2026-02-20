import 'package:flutter/material.dart';
import 'google_stt_service.dart';
import 'result_screen.dart';
import 'agreement_screen.dart';

void main() {
  runApp(const MedexSTTDemo());
}

class MedexSTTDemo extends StatelessWidget {
  const MedexSTTDemo({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: AgreementScreen(),
    );
  }
}

class STTHomePage extends StatefulWidget {
  const STTHomePage({super.key});

  @override
  State<STTHomePage> createState() => _STTHomePageState();
}

class _STTHomePageState extends State<STTHomePage> {
  
  final GoogleSttService _googleStt = GoogleSttService();
  String _recognizedText = "버튼을 누르고 진료 기록을 녹음하세요.";
  bool _isAnalyzing = false;

  Future<void> _testGoogleStt() async {
    setState(() {
      _isAnalyzing = true;
      _recognizedText = "구글 서버로 요청 보내는 중...";
    });

    try {
      // 가짜 음성 데이터
      const String fakeAudio = "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=";
      final String result = await _googleStt.convertAudioToText(fakeAudio);

      setState(() {
        _recognizedText = "통신 성공! 결과: $result";
      });

      Future.delayed(const Duration(seconds: 1), () {
        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (context) => const ResultScreen()),
          );
        }
      });
    } catch (e) {
      setState(() {
        _recognizedText = "통신 실패: $e";
      });
    } finally {
      setState(() => _isAnalyzing = false);
    }
  }

  @override
Widget build(BuildContext context) {
  return Scaffold(
    appBar: AppBar(title: const Text("진료 기록 음성 녹음")),
    body: SingleChildScrollView(
      child: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Padding(
              padding: const EdgeInsets.all(20),
              child: Text(_recognizedText, textAlign: TextAlign.center, style: const TextStyle(fontSize: 18)),
            ),
            if (_isAnalyzing) const CircularProgressIndicator(),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _isAnalyzing ? null : _testGoogleStt,
              child: const Text("녹음하기"),
            ),
          ],
        ),
      ),
    ),
  );
}
}