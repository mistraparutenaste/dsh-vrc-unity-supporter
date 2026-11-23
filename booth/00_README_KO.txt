VRChat Avatar (Unity) - dsh-vrc-unity-supporter  버전 {{VERSION}}
====================================================================

AI 에이전트(DeepSeek Harness / Claude Code / Codex)가 VRChat 아바타
개변을 돕도록 하는 플러그인입니다. Unity를 열지 않고 프로젝트를 조사하고,
변경은 Unity Editor 스크립트로 적용한 뒤 결과를 확인합니다.
업로드는 하지 않습니다.

AI 에이전트는 기본적으로 일본어로 답합니다. 한국어로 요청하면
한국어로 답합니다.


■ 먼저 꼭 확인해 주세요
--------------------------------------------------------------------

・이 플러그인은 무료이지만, 사용하려면 AI 에이전트 앱과
  그 이용료(유료 플랜이나 API 요금)가 따로 필요합니다.

・지원하는 Unity는 2022.3.22f1입니다(VRChat SDK가 제작자용으로 지원하는 버전).
  Unity 6 프로젝트는 지원하지 않습니다.

・개변하기 전에 프로젝트를 백업해 주세요.
  플러그인은 적용 전에 Git으로 복원 지점을 만들고, 내용을 보여 주며
  승인을 받지만, 모든 실패를 막을 수는 없습니다.


■ 필요한 것(Windows 10 / 11)
--------------------------------------------------------------------

  ・AI 에이전트 앱(하나)
      DeepSeek Harness Desktop / Claude Code / Codex
  ・Git for Windows
  ・Python 3.10 이상
  ・Unity Hub와 Unity 2022.3.22f1(라이선스를 활성화한 것)
  ・VCC 또는 ALCOM으로 관리하는, VRChat SDK - Avatars가 들어 있는 프로젝트

  기능에 따라 VRCFury, Modular Avatar, Avatar Optimizer,
  PhotoCraft, Blender도 필요합니다.


■ 압축을 풀기 전에
--------------------------------------------------------------------

  다운로드한 ZIP을 마우스 오른쪽 버튼으로 클릭 → 속성 → 아래의
  「차단 해제」에 체크 → 확인을 누른 뒤 압축을 풀어 주세요.
  압축을 푼 폴더는 지우지 않을 곳(예: 문서 안)에 두세요.
  Claude Code와 Codex는 이 폴더에서 플러그인을 읽어 들입니다.


■ 설치 방법
--------------------------------------------------------------------

가장 쉬운 방법은 AI 에이전트에게 맡기는 것입니다. 이 폴더를 작업 폴더로
AI 에이전트 앱을 열고, 다음 문장을 보내 주세요.

  이 폴더에 있는 00_README_KO.txt를 읽고, 그 설치 순서에 따라
  내가 쓰고 있는 앱에 플러그인을 설치하도록 도와줘.
  명령을 실행하기 전에는 매번 나에게 물어보고,
  내가 직접 해야 하는 부분에서는 기다려 줘.

직접 설치하는 경우에는 사용하는 앱에 맞춰 아래 중 하나를 실행합니다.
아래의 <폴더>는 이 README가 있는 폴더의 전체 경로로 바꿉니다
(폴더를 Shift + 마우스 오른쪽 클릭 →「경로로 복사」로 얻을 수 있습니다).

[DeepSeek Harness]
  1. DeepSeek Harness를 종료합니다(작업 표시줄 알림 영역에서도).
  2. 이 폴더의 install.cmd를 더블클릭합니다.
  3. 완료되었다고 표시되면 실행하고, 새 세션에서
     프리셋 「VRChat Avatar」를 선택합니다.
  ※ install.cmd는 인터넷(npm)에서 공개된 버전을 받아 옵니다.
    이 ZIP보다 새 버전이 설치될 수 있습니다.

[Claude Code]
  PowerShell에서 다음 두 명령을 순서대로 실행하고, 새 세션을 시작합니다.

    claude plugin marketplace add "<폴더>"
    claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter

[Codex]
  PowerShell에서 다음을 실행하고 Codex 앱을 다시 연 뒤,
  Plugins에서 「VRChat Avatar (Unity)」를 설치합니다.

    codex plugin marketplace add "<폴더>"

  ※ Codex 버전은 아직 작자의 환경에서 동작을 확인하지 않았습니다.

새 버전을 자동으로 받고 싶다면 <폴더> 대신
  mistraparutenaste/dsh-vrc-unity-supporter
를 지정하면 GitHub에서 설치할 수 있습니다.


■ 새 버전으로 업데이트하기
--------------------------------------------------------------------

  1. 새 ZIP의 압축을 풀고, 안에 있는 dsh-vrc-unity-supporter 폴더로
     전에 둔 폴더를 통째로 바꿉니다(위치는 바꾸지 마세요).
  2. 사용하는 앱에 맞춰 PowerShell에서 다음을 실행합니다.

  [Claude Code]
    claude plugin marketplace update dsh-vrc-unity-supporter
    claude plugin update dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
  [Codex]
    codex plugin marketplace upgrade dsh-vrc-unity-supporter
  [DeepSeek Harness]
    Plugins에서 dsh-vrc-unity-supporter를 업데이트합니다.

  3. 새 세션(Codex에서는 새 스레드)을 시작합니다.


■ 처음 해 볼 것
--------------------------------------------------------------------

  1. 개변하려는 Unity 프로젝트 폴더(Assets와 ProjectSettings가 있는
     폴더)를 앱의 작업 폴더로 엽니다.
  2. 채팅에 「이 프로젝트의 아바타 구성을 조사해 줘」라고 보냅니다.
     이 단계에서는 프로젝트의 파일을 읽기만 합니다.
  3. 개변을 요청할 때는 Unity에서 씬을 저장하고 Unity를 닫아 주세요.

  자세한 사용법은 README.md(일본어)를 보세요. 영어 소개는
  docs/DETAIL.md에 있습니다. AI 에이전트에게 무엇을 할 수 있는지
  물어봐도 됩니다.


■ 동작 확인 상황(버전 {{VERSION}} 시점)
--------------------------------------------------------------------

작자의 환경(Windows 11, Unity 2022.3.22f1, VRCFury 1.1475.0,
Modular Avatar 1.18.7, Avatar Optimizer 1.9.23)에서 확인한 것:

  ・프로젝트 진단(여러 아바타가 있는 프로젝트)
  ・배치된 의상의 토글, 토글 제거
  ・소품과 머리카락을 본에 붙이기, 떼기
  ・다른 아바타용 의상을 Blender로 맞춰서 입히기(어깨, 소매, 신발 위치)
  ・의상에 포함된 PSD로 색상 바리에이션 만들기, 목록 보기, 삭제
  ・lilToon 값(색조 보정, 림 라이트, 윤곽선)을 바꾼 복제본의 전후 촬영 비교
    (lilToon 2.4.1. 메뉴에 적용하는 것은 미확인)
  ・체형 조정, 옷 아래에 가려지는 몸 삭제, 그 되돌리기
  ・퍼포먼스 랭크 추정
  모두 Unity에서의 적용과 SDK 전처리(빌드)까지 확인했습니다.

아직 확인하지 않은 것:

  ・VRChat 안에서의 모습과 움직임(업로드해서 확인하는 것은 사용자입니다)
  ・배타 토글(한쪽을 켜면 다른 쪽이 꺼짐)의 Gesture Manager와
    VRChat 안에서의 동작
  ・피부, 머리카락, 눈의 PSD로 만드는 색상 바리에이션
  ・다른 아바타용 의상에 Blendshape Sync를 붙여 옷 아래의 몸을 지우는 순서
  ・Codex 버전의 동작 전반
  ・lilToon 조정을 메뉴에 적용하는 것과 VRChat 안에서의 모습

확인한 아바타는 한정되어 있습니다. 다른 아바타나 의상에서는
잘 되지 않을 수 있습니다.


■ 문제가 생겼을 때・문의
--------------------------------------------------------------------

  README.md(일본어)의 「困ったとき」(문제 해결)를 보거나,
  AI 에이전트에게 문제를 조사해 달라고 요청하세요.
  문제 보고는 다음 중 하나로 부탁드립니다.
    ・GitHub Issues
      https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/issues
    ・BOOTH 메시지
  답변이나 수정 시기는 약속할 수 없습니다.


■ 라이선스・면책
--------------------------------------------------------------------

  ・MIT 라이선스입니다(LICENSE). 수정하고 재배포할 수 있습니다.
  ・보증하지 않습니다. 사용으로 인해 생긴 손해에 대해 작자는 책임지지 않습니다.
  ・이 플러그인은 VRChat Inc., Unity Technologies, 각 패키지의 작자와
    관계가 없습니다. VRChat과 Unity는 각 회사의 상표입니다.
  ・아바타, 의상, 머리카락 등의 소재는 포함되어 있지 않습니다. 소재의 이용
    약관은 각 작자의 약관을 따르세요. 포함된 PSD로 만든 텍스처 등
    소재로 만든 것을 배포하지 마세요.
  ・이 플러그인은 AI의 도움을 받아 개발했습니다.
