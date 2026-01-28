import 'package:flutter/material.dart';

class ResultScreen extends StatefulWidget {
  const ResultScreen({super.key});

  @override
  State<ResultScreen> createState() => _ResultScreenState();
}

class _ResultScreenState extends State<ResultScreen> {
  // 임시 더미 데이터 [나중에 받아야 할 서버 응답 JSON 데이터 구조]
  final Map<String, dynamic> responseData = {
    "summary_3sent": [
      "만성 신장 질환 3단계로, 칼륨 섭취 조절이 가장 중요합니다.",
      "처방된 약은 식후 30분에 규칙적으로 복용해야 합니다.",
      "다음 진료는 2주 뒤 수요일 오전 10시입니다."
    ],
    "easy_terms": [
      {"term": "사구체 여과율", "desc": "콩팥이 노폐물을 걸러내는 능력을 말합니다."},
      {"term": "부종", "desc": "몸이 붓는 현상을 말합니다."}
    ],
    "next_actions": [
      "매일 아침 공복에 몸무게 측정하기",
      "저염식 식단 지키기 (소금 하루 5g 이하)",
      "하루 1.5리터 이상 수분 섭취 제한"
    ],
    "warnings": [
      "갑작스러운 호흡 곤란 시 즉시 응급실 방문",
      "칼륨이 높은 바나나, 참외 섭취 주의"
    ]
  };

  // 체크리스트 상태 설정
  late List<bool> _actionChecks;

  @override
  void initState() {
    super.initState();
    _actionChecks = List<bool>.filled(responseData['next_actions'].length, false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("진료 요약 결과")),
      body: ListView(
        padding: const EdgeInsets.all(16.0),
        children: [
          _buildSummaryCard(responseData['summary_3sent']),
          _buildEasyTermsCard(responseData['easy_terms']),
          _buildActionCard(responseData['next_actions']),
          _buildWarningCard(responseData['warnings']),
        ],
      ),
    );
  }

  // 1. 3문장 요약 카드
  Widget _buildSummaryCard(List<dynamic> sentences) {
    return Card(
      color: Colors.blue[50],
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("요약 결과", style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const Divider(),
            ...sentences.map((s) => Text("• $s", style: const TextStyle(fontSize: 16, height: 1.5))),
          ],
        ),
      ),
    );
  }

  // 2. 쉬운 말 용어 카드
  Widget _buildEasyTermsCard(List<dynamic> terms) {
    return Card(
      child: ExpansionTile(
        title: const Text("쉬운 용어 풀이", style: TextStyle(fontWeight: FontWeight.bold)),
        children: terms.map((t) => ListTile(
          title: Text(t['term'], style: const TextStyle(fontWeight: FontWeight.bold)),
          subtitle: Text(t['desc']),
        )).toList(),
      ),
    );
  }

  // 3. 환자 행동 가이드 (체크리스트 기능 포함)
  Widget _buildActionCard(List<dynamic> actions) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("환자 행동 가이드", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ...List.generate(actions.length, (index) => CheckboxListTile(
              value: _actionChecks[index],
              onChanged: (val) {
                setState(() => _actionChecks[index] = val!);
              },
              title: Text(actions[index]),
              controlAffinity: ListTileControlAffinity.leading,
              contentPadding: EdgeInsets.zero, // 간격 최적화
            )),
          ],
        ),
      ),
    );
  }

  // 4. 주의사항
  Widget _buildWarningCard(List<dynamic> warnings) {
    return Card(
      color: Colors.red[50],
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("주의사항", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.red)),
            ...warnings.map((w) => Padding(
              padding: const EdgeInsets.only(top: 8.0),
              child: Text("! $w", style: const TextStyle(color: Colors.redAccent, fontSize: 15)),
            )),
          ],
        ),
      ),
    );
  }
}
