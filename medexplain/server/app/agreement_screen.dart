import 'package:flutter/material.dart';
import 'main.dart';

class AgreementScreen extends StatefulWidget {
  const AgreementScreen({super.key});

  @override
  State<AgreementScreen> createState() => _AgreementScreenState();
}

class _AgreementScreenState extends State<AgreementScreen> {
  bool _isAgreed = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("서비스 이용 동의")),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("MedExplain 이용을 위해\n동의가 필요합니다.", 
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 30),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(15),
                decoration: BoxDecoration(
                  color: Colors.grey[100],
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const SingleChildScrollView(
                  child: Text(
                    "1. 개인정보 수집 및 이용\n본 서비스는 정확한 의료 상담 기록 및 요약을 위해 음성 데이터를 수집하고 서버로 전송합니다.\n\n"
                    "2. AI 번역 및 요약 면책 조항 (중요)\n본 시스템이 제공하는 번역 및 요약 결과는 AI 모델에 의한 것으로, 100% 정확하지 않을 수 있습니다. "
                    "특히 빨간색(⚠️)으로 표시된 부분은 오역의 위험이 있으니 반드시 의료진과 직접 확인하시기 바랍니다.\n\n"
                    "3. 책임 한계\n번역 결과에 기반한 의학적 판단의 최종 책임은 사용자 및 의료진에게 있으며, 본 서비스는 법적 책임을 지지 않습니다.",
                    style: TextStyle(fontSize: 14, height: 1.6),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 20),
            CheckboxListTile(
              title: const Text("위 약관 및 면책 조항에 동의합니다."),
              value: _isAgreed,
              onChanged: (val) => setState(() => _isAgreed = val!),
              controlAffinity: ListTileControlAffinity.leading,
            ),
            SizedBox(
              width: double.infinity,
              height: 55,
              child: ElevatedButton(
                onPressed: _isAgreed 
                  ? () {
                      Navigator.pushReplacement(
                        context, 
                        MaterialPageRoute(builder: (_) => const STTHomePage())
                      );
                    }
                  : null,
                style: ElevatedButton.styleFrom(backgroundColor: Colors.blue),
                child: const Text("동의하고 시작하기", style: TextStyle(color: Colors.white, fontSize: 18)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}