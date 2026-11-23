# dsh-vrc-unity-supporter

[日本語](README.md) | [English](README.en.md) | [简体中文](README.zh-CN.md) | 한국어

AI 에이전트를 사용해 VRChat 아바타를 개변하기 위한 플러그인입니다.

AI 에이전트는 기본적으로 일본어로 답합니다. 한국어로 요청하면 한국어로 답합니다.

## 설치 방법

### AI 에이전트에게 맡기기(추천)

DSH, Claude Code, Codex 중 하나의 채팅에 다음 문장을 그대로 붙여 넣어 보내 주세요. 부족한 것의 확인, 플러그인 설치, 첫 확인까지 에이전트가 순서대로 안내합니다.

```text
VRChat 아바타 개변에 「dsh-vrc-unity-supporter」라는 플러그인을 쓰고 싶습니다.
Windows PC에서 설치부터 첫 확인까지 다음 순서로 도와주세요.
하나씩 진행하고, 내가 직접 해야 하는 부분에서는 기다려 주세요.

1. 다음이 설치되어 있는지 명령으로 확인해 주세요.
   Git / Python 3.10 이상 / Unity Hub와 Unity 2022.3.22f1 / VCC 또는 ALCOM
   부족한 것은 공식 다운로드 페이지를 알려 주고, 내가 설치할 때까지 기다려 주세요.
   직접 설치하지는 마세요.
2. 지금 쓰고 있는 앱이 DeepSeek Harness, Claude Code, Codex 중 무엇인지 확인하고 플러그인을 설치해 주세요.
   - Claude Code인 경우(데스크톱 앱 포함):
     다음 두 명령을 PowerShell에서 실행해도 되는지 나에게 물어본 뒤 실행해 주세요.
       claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
       claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
     claude 명령을 찾을 수 없으면 https://code.claude.com/docs/en/setup 의
     Windows용 순서를 알려 주고, 내가 설치할 때까지 기다려 주세요.
   - Codex인 경우:
     다음 명령을 PowerShell에서 실행해도 되는지 나에게 물어본 뒤 실행해 주세요.
       codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
     그다음 Codex 앱의 Plugins에서 「VRChat Avatar (Unity)」를 설치하는 방법을 안내해 주세요.
     codex 명령을 찾을 수 없으면 https://developers.openai.com/codex/ 의 순서를 알려 주고,
     내가 설치할 때까지 기다려 주세요.
   - DeepSeek Harness인 경우:
     Plugins → Add plugin에 「dsh-vrc-unity-supporter」를 추가하는 방법을 안내해 주세요.
3. 개변하려는 Unity 프로젝트 폴더(Assets와 ProjectSettings가 있는 폴더)를 나에게 물어봐 주세요.
4. 마지막으로, 그 폴더에서 새 세션을 시작하고 다음 문장을 보내라고 알려 주세요.
   「이 프로젝트의 아바타 구성을 조사해 줘」

그때까지 Unity 프로젝트의 파일은 변경하지 마세요.

GitHub 저장소 URL: https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/tree/master
```

플러그인은 설치한 뒤에 시작한 새 세션에서 사용할 수 있습니다.

### DSH에서 설치하기

1. DSH를 열고 **Plugins** → **Add plugin**을 선택합니다.
2. 입력란에 다음 패키지 이름을 붙여 넣고 설치합니다.

   ```text
   dsh-vrc-unity-supporter
   ```

3. **새 세션**을 만들고, 프리셋 목록에 **VRChat Avatar**가 표시되는지 확인합니다.

<details>
<summary>ZIP으로 설치하는 경우</summary>

1. 이 GitHub 페이지에서 **Code** → **Download ZIP**을 선택합니다.
2. 다운로드한 ZIP을 마우스 오른쪽 버튼으로 클릭하고 **압축 풀기**를 선택합니다.
3. DSH를 종료하고, 압축을 푼 폴더에 있는 **`install.cmd`** 파일을 더블클릭합니다.
4. 완료되었다고 표시되면 DSH를 다시 실행하고 **새 세션**에서 **VRChat Avatar**를 선택합니다.

`install.cmd`는 DSH에 포함된 명령을 사용해 npm에서 공개된 버전을 받아 설치합니다. 설치하는 동안 인터넷에 연결해 두세요. [설치 프로그램의 자세한 내용과 삭제 방법(일본어)](installer/README.md)

</details>

### Claude Code에서 설치하기

Claude Code는 **Claude 데스크톱 앱의 Code 탭**과 터미널 버전 모두에서 사용할 수 있습니다.

**데스크톱 앱을 사용하는 경우**

1. PowerShell을 열고 다음 두 명령을 순서대로 실행합니다.

   ```powershell
   claude plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   ```powershell
   claude plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
   ```

   `claude`를 찾을 수 없다고 표시되면, [Claude Code 설치](https://code.claude.com/docs/en/setup)의 Windows용 순서로 `claude` 명령을 설치한 뒤 다시 실행합니다.
2. 데스크톱 앱의 **Code** 탭에서 Unity 프로젝트 폴더를 선택해 새 세션을 시작합니다.
3. 입력란 옆의 **+** → **Plugins** → **Manage plugins**에 `dsh-vrc-unity-supporter`가 표시되고 활성화되어 있는지 확인합니다.

**터미널 버전을 사용하는 경우**

Unity 프로젝트 폴더에서 Claude Code를 열고 다음을 순서대로 실행합니다.

```text
/plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
/plugin install dsh-vrc-unity-supporter@dsh-vrc-unity-supporter
```

설치한 뒤 `/reload-plugins`를 실행하거나 새 세션을 시작합니다.

### Codex에서 설치하기

1. PowerShell을 열고 다음을 실행해 마켓플레이스를 추가합니다.

   ```powershell
   codex plugin marketplace add mistraparutenaste/dsh-vrc-unity-supporter
   ```

   `codex`를 찾을 수 없다고 표시되면, [Codex 문서](https://developers.openai.com/codex/)의 순서로 `codex` 명령을 설치한 뒤 다시 실행합니다.
2. Codex 앱을 다시 열고, **Plugins**에서 마켓플레이스 `dsh-vrc-unity-supporter`를 선택해 **VRChat Avatar (Unity)** 플러그인을 설치합니다.
3. Unity 프로젝트 폴더에서 새 스레드를 시작합니다.

Codex에서는 스킬의 명령이 샌드박스 안에서 실행됩니다. Unity나 Blender를 실행할 때, 샌드박스 밖에서 실행해도 되는지 물어볼 수 있습니다. 무엇을 실행하는지 확인한 뒤 승인해 주세요.

### 필요한 것

AI 에이전트에게 맡기는 경우에는 에이전트가 확인합니다. 직접 준비하는 경우에는 Windows에서 다음을 갖춰 주세요.

| 필요한 것 | 준비할 것 |
| --- | --- |
| **DeepSeek Harness Desktop, Claude Code, Codex 중 하나** | DSH는 공식 사이트의 **Download Desktop → Windows (64-bit)** 메뉴에서 설치하고, 화면 안내에 따라 초기 설정을 마칩니다. Claude Code는 데스크톱 앱이나 터미널 버전을 사용합니다. Codex는 앱과 `codex` 명령을 사용합니다. [DSH 공식 사이트](https://www.deepseek.com/en/harness/) · [Claude Code 개요](https://code.claude.com/docs/en/overview) · [Codex 문서](https://developers.openai.com/codex/) |
| **Git for Windows** | 개변 전의 상태를 기록해 나중에 되돌리기 위해 사용합니다. 기록은 PC 안에서만 이루어집니다. [Git 다운로드](https://git-scm.com/install/win) |
| **Python 3.10 이상** | 아바타의 구성을 조사하기 위해 사용합니다. 설치한 뒤 사용하는 앱(DSH, Claude Code, Codex)을 다시 열어 주세요. [Windows용 Python 다운로드](https://www.python.org/downloads/windows/) |
| **Unity Hub와 Unity 2022.3.22f1** | Unity Hub에서 유효한 라이선스를 설정하고, 지정된 버전으로 프로젝트를 열 수 있는지 확인합니다. [VRChat 공식 Unity 설치 안내](https://creators.vrchat.com/sdk/upgrade/current-unity-version/) |
| **VCC 또는 ALCOM과 아바타 프로젝트** | 평소에 쓰는 관리 앱 중 하나를 사용합니다. 작업 대상은 **VRChat SDK - Avatars**가 설치되어 있고 Unity에서 열 수 있는 프로젝트입니다. [VCC 설정](https://vcc.docs.vrchat.com/guides/getting-started/) · [ALCOM 다운로드](https://vrc-get.anatawa12.com/alcom/) |

기능에 따라 그 밖에도 필요한 것이 있습니다(VRCFury, Modular Avatar, Avatar Optimizer, PhotoCraft, Blender). [할 수 있는 것](#할-수-있는-것)의 표를 봐 주세요.

## 해 보기

1. 개변하려는 Unity 프로젝트 폴더를 엽니다. `Assets`, `Packages`, `ProjectSettings`가 있는 폴더입니다. DSH에서는 워크스페이스로, Claude Code와 Codex에서는 작업 폴더로 엽니다.
2. DSH에서는 새 세션의 프리셋을 **VRChat Avatar**, 모델을 **DeepSeek V4.1 Flash**, 에포트를 **MAX**로 설정합니다. Claude Code에서는 새 세션을, Codex에서는 새 스레드를 시작하기만 하면 됩니다.
3. 채팅에 다음 문장을 보냅니다. 이 단계에서는 프로젝트의 파일을 읽기만 합니다.

   ```text
   이 프로젝트의 아바타 구성을 조사해 줘
   ```

4. 아바타와 의상을 확인했으면, 의상 이름을 자신의 프로젝트에 있는 것으로 바꿔서 요청합니다. 적용하기 전에 씬을 저장하고 Unity를 닫아 주세요.

   ```text
   Outfit_Hoodie를 「의상/후드티」에서 켜고 끌 수 있게 해 줘. 처음 상태는 켜짐으로
   ```

5. 에이전트가 대상과 변경 예정을 보여 주므로, 확인한 뒤 적용을 요청합니다. 의상 이름이 모호하면 저장된 씬에서 후보를 골라 물어봅니다.
6. 적용하면 저장 결과와, SDK 전처리에서 메뉴와 애니메이션을 확인했는지가 표시됩니다. VRChat 안에서 시험해 보려면 Unity에서 **VRChat SDK → Show Control Panel → Builder → Offline Testing → Build & Test**를 선택합니다. VRChat의 **SDK Test Avatars**에서 테스트용 아바타를 고르고, 메뉴에서 의상을 켜고 꺼 보세요. [VRChat 로컬 테스트 순서](https://creators.vrchat.com/avatars/#local-avatar-testing)

## 할 수 있는 것

| 할 수 있는 것 | 요청 예 | 추가로 필요한 것 |
| --- | --- | --- |
| 아바타 구성 조사 | 「이 프로젝트의 아바타 구성을 조사해 줘」 | 없음 |
| 메뉴에서 의상 전환 | 「Outfit_Hoodie를 『의상/후드티』에서 켜고 끌 수 있게 해 줘」 | VRCFury |
| 색상 바리에이션 만들기 | 「후드티를 남색으로 바꾼 색상 바리에이션을 만들어 줘」 | PhotoCraft, 아바타에 포함된 PSD |
| lilToon의 색, 그림자, 윤곽선 조정 | 「머리카락 그림자를 옅게 하고 윤곽선을 가늘게 해 줘」 | VRCFury, lilToon 또는 Poiyomi 머티리얼 |
| 체형 조정과 관통 수정 | 「옷 아래의 몸을 지우고 가슴을 조금 크게 해 줘」 | Modular Avatar, Avatar Optimizer |
| 소품, 머리카락, 의상 붙이기 | 「이 울프컷 머리를 붙여 줘」 | Modular Avatar |
| Blender로 만들기, 비대응 의상 입히기 | 「Selestia용 이 코트를 Salt에게 입혀 줘」 | Blender, Modular Avatar |
| 흔들리는 부분 조정 | 「뒷머리가 더 부드럽게 흔들리게 하고, 꼬리는 잡을 수 없게 해 줘」 | 없음 |
| 시점과 부분 크기 변경 | 「시점이 낮으니 고쳐 줘. 머리를 조금 크게 해 줘」 | 손이나 가슴만 바꿀 때는 Modular Avatar |
| 표정 바꾸기 | 「오른손 주먹을 웃는 얼굴로 해 줘. 메뉴에서 게슴츠레한 눈으로 고정할 수 있게 해 줘」 | Modular Avatar |
| 아바타 업데이트에 개변 이어 가기 | 「Salt를 새 버전으로 바꿨으니 개변을 이어 가 줘」 | 없음(각 개변에 필요한 것 제외) |
| 퍼포먼스 랭크와 파라미터 용량 조사 | 「퍼포먼스 랭크를 조사해 줘」「파라미터가 몇 bit 남았어?」 | 없음 |

VRCFury, Modular Avatar, Avatar Optimizer는 VCC 또는 ALCOM으로 대상 프로젝트에 넣습니다. [VRCFury 설치 순서](https://vrcfury.com/download/)

### 메뉴에서 의상 전환

씬에 배치한 의상을 VRChat 메뉴에서 켜고 끌 수 있게 합니다. 아바타와 의상을 같은 씬에 배치하고 저장해 두세요.

```text
Outfit_Hoodie를 「의상/후드티」에서 켜고 끌 수 있게 해 줘. 처음 상태는 켜짐으로
```

- **한 벌만 입기**: 「후드티와 코트를 한 벌만 입도록 전환할 수 있게 해 줘」라고 요청하면 같은 그룹의 토글이 됩니다. 한쪽을 켜면 다른 쪽이 꺼집니다.
- **목록과 제거**: 만든 토글은 「의상 토글을 목록으로 보여 줘」로 확인할 수 있습니다. 「후드티 토글을 떼 줘」라고 요청하면 그 토글만 제거합니다(의상 자체는 남습니다).

### 색상 바리에이션 만들기

아바타나 의상에 포함된 레이어 PSD로 색상 바리에이션을 만듭니다. 의상, 피부, 머리카락, 눈의 색을 바꾸거나, 직접 준비한 로고나 무늬를 넣을 수 있습니다. 원래의 PSD, 텍스처, 머티리얼은 그대로 남고, 색상 바리에이션은 별도의 머티리얼로 추가됩니다. 메뉴에서 원래 모습과 전환할 수 있습니다.

```text
후드티를 남색으로 바꾼 색상 바리에이션을 만들어 줘. PSD는 Downloads\Salt_v1.0.1에 있어
```

에이전트는 PSD의 레이어 구성을 조사하고, 어떤 레이어를 어떻게 바꿀지 보여 준 뒤 내보냅니다. 이어서 Unity에서 아바타를 촬영하고, 개변 전후를 나란히 놓은 이미지로 확인합니다. 만든 색상 바리에이션은 「색상 바리에이션을 목록으로 보여 줘」로 확인할 수 있고, 「Hoodie_Blue 색상 바리에이션을 삭제해 줘」로 뗄 수 있습니다.

- 무료 이미지 편집 소프트웨어 **PhotoCraft**를 설치해 둡니다. PSD 편집은 명령줄로 하므로 창을 열 필요는 없습니다. [PhotoCraft 다운로드](https://getartcraft.com/apps/photocraft) · [자세한 사용법(일본어)](docs/PHOTOCRAFT.md)
- 포함된 PSD로 만든 텍스처는 많은 아바타의 이용 약관에서 배포가 금지되어 있습니다. 프로젝트 안에서만 사용해 주세요.

### lilToon의 색, 그림자, 윤곽선 조정

PSD가 없는 의상이나 머리카락도 lilToon 머티리얼의 값으로 모습을 조정할 수 있습니다. Poiyomi Toon(9, 10, 잠그지 않은 것) 머티리얼에도 사용할 수 있습니다. 바꿀 수 있는 것은 주색과 색조 보정(색상, 채도, 밝기), 그림자의 색과 강도, 윤곽선의 색과 굵기, 발광, 림 라이트, 매트캡, 밝기의 상한과 하한입니다. 원래 머티리얼은 그대로 남고, 값을 바꾼 복제본이 추가됩니다. 메뉴에서 원래 모습과 전환할 수 있습니다.

```text
머리카락 그림자를 옅게 하고 윤곽선을 가늘게 해 줘. 계속 이 모습으로 하고 싶어
```

에이전트는 지금 표시되고 있는 머리카락이나 의상의 머티리얼과 현재 값을 조사하고, 바꿀 값(전 → 후)을 보여 줍니다. 이어서 개변 전후를 나란히 놓은 이미지로 확인하고, 승인을 받은 뒤 적용합니다. 「계속 이 모습으로」라고 요청하면 처음 상태를 켜짐으로 합니다(메뉴에서 끄면 원래대로 돌아갑니다). 떼는 방법은 색상 바리에이션과 같습니다.

- 검은색, 흰색, 회색 머리카락이나 옷은 색 자체가 없어서 색상이나 채도를 바꿔도 거의 달라지지 않습니다. 밝기나 림 라이트, 윤곽선으로 조정하거나 PSD로 색상 바리에이션을 만들어 주세요.
- 렌더링 모드, 투명, 스텐실 같은 값은 바꾸지 않습니다. lilToon과 Poiyomi 이외의 셰이더(UnityChan Toon Shader 등)는 아직 지원하지 않습니다.

### 체형 조정과 관통 수정

FBX를 바꾸지 않고 아바타의 형태를 조정합니다.

- **체형과 얼굴**: 아바타에 포함된 셰이프 키(가슴 크기, 허리 등)의 값을 바꿉니다.
- **의상이 따라오게**: 체형을 바꿨을 때 의상의 대응하는 셰이프 키가 몸에 맞춰 움직이도록 합니다(Modular Avatar의 Blendshape Sync).
- **가려지는 부분 삭제**: 옷 아래에 가려지는 몸의 메시를 빌드할 때 삭제합니다(Avatar Optimizer의 Remove Mesh By BlendShape). 관통이 잘 일어나지 않고 폴리곤 수도 줄어듭니다.

```text
후드티를 입고 있을 때 옷 아래의 몸을 지우고, 가슴을 조금 크게 해 줘
```

에이전트가 셰이프 키를 조사해 바꿀 값과 지울 부위를 보여 줍니다. 그다음 VRChat과 같은 방식으로 빌드한 개변 전후 이미지와 삼각형 수를 보여 주고, 승인을 받은 뒤 적용합니다. 「Fit_Hoodie 체형 조정을 되돌려 줘」로 되돌릴 수 있습니다. 되돌리는 것은 이 플러그인이 바꾼 값과 추가한 설정뿐이며, 아바타에 처음부터 들어 있던 연동은 남습니다.

### 소품, 머리카락, 의상 붙이기

기존의 모자, 머리카락, 소품, 의상(prefab이나 FBX)을 아바타에 붙입니다.

- **본에 붙이기**: 모자나 리본, 아바타용 머리카락을 머리 등의 본에 붙입니다(Modular Avatar의 Bone Proxy).
- **골격 통합**: 의상처럼 골격을 가진 것은 아바타의 골격에 통합합니다(Modular Avatar의 Setup Outfit).
- **메뉴에서 넣고 빼기**: 붙인 소품을 메뉴에서 켜고 끌 수 있고, 착용하는 동안만 원래 머리카락 등을 숨길 수 있습니다.
- **손에 들기, 내려놓기**: 검이나 컵 같은 소품을 손에 들게 하고, 메뉴의 「내려놓기」로 그 자리에 남길 수 있습니다. 월드에 고정해 두는 소품도 만들 수 있습니다.

```text
이 울프컷 머리를 붙이고, 원래 머리는 메뉴에서 전환할 수 있게 해 줘
```

에이전트가 후보와 본을 조사해 붙이는 방법을 보여 주고, VRChat과 같은 방식으로 빌드한 개변 전후 이미지로 위치를 확인한 뒤, 승인을 받아 적용합니다. 「붙인 소품을 목록으로 보여 줘」「WolfHair를 떼 줘」라고 요청할 수도 있습니다.

### Blender로 만들기, 비대응 의상 입히기

**Blender**를 설치해 두면 다음도 할 수 있습니다. Blender는 백그라운드에서 동작하므로 창은 열리지 않습니다.

- **간단한 형태 만들기**: 구, 정육면체, 원기둥, 원뿔, 고리를 조합해 리본이나 뿔 같은 소품을 만듭니다.
- **비대응 의상 입히기**: 다른 아바타용으로 만들어진 머리카락이나 의상을 이 아바타의 골격에 맞춰 변형하고, 몸에 파고든 부분을 바깥으로 밀어냅니다. 의상이 만들어진 원래 아바타의 FBX가 있으면 가슴, 허리, 팔 굵기 등의 체형 차이도 의상에 옮깁니다. 아바타의 체형 키(`Breasts_big` 등)를 의상에도 만들기 때문에, 체형을 바꿔도 의상이 따라옵니다. 붙인 뒤에는 옷 아래에 가려지는 몸의 삭제와, 빌드한 전후 촬영까지 이어서 진행합니다.

```text
Selestia용 이 코트를 Salt에게 입혀 줘. 원래 소체는 Assets/Booth/SELESTIA.fbx에 있어
```

자동으로 맞출 수 있는 것은 골격의 위치, 방향, 길이, 원래 아바타와의 체형 차이, 몸에서 밀어내기, 체형 키 따라가기까지입니다. 길이나 체형 차이가 큰 부분은 Blender에서 직접 작업해야 할 수 있습니다. 다른 아바타용 의상을 사용해도 되는지는 각 이용 약관을 확인해 주세요.

Blender는 [blender.org](https://www.blender.org/download/)에서 무료로 설치할 수 있습니다(`winget install BlenderFoundation.Blender`로도 가능).

### 흔들리는 부분 조정

아바타에 붙어 있는 PhysBone의 값으로 머리카락, 치마, 꼬리 등이 흔들리는 방식을 조정합니다. 원래 prefab은 바꾸지 않고 씬에 저장합니다.

- **흔들림**: 「부드럽게」「단단하게」「무겁게 늘어지게」 같은 프리셋에서 시작해 당기는 힘, 중력 등을 세세하게 바꿀 수 있습니다.
- **잡기와 포즈**: 다른 사람이 잡거나 포즈를 줄 수 없게 할 수 있습니다.
- **관통 방지**: 허벅지나 몸에 콜라이더를 추가해 치마나 끈이 다리를 뚫고 나가지 않게 합니다.

```text
뒷머리가 더 부드럽게 흔들리게 하고, 꼬리는 잡을 수 없게 해 줘
```

에이전트는 흔들리는 부분과 값(각각 움직이는 본의 수 포함)을 목록으로 보여 주고, 바꿀 값(전 → 후)을 보여 준 뒤 적용합니다. 흔들림은 이미지로 확인할 수 없으므로 적용 후 Gesture Manager나 VRChat에서 흔들어 확인해 주세요. 「SoftHair 흔들림 조정을 되돌려 줘」라고 하면 되돌립니다.

### 시점과 부분 크기 변경

- **뷰 포지션**: 1인칭 시점을 두 눈 사이에 다시 두거나 조금 올리고 내립니다.
- **부분 크기**: 머리를 조금 크게, 손을 조금 작게처럼 본 단위로 크기를 바꿉니다. 머리를 키우면 머리카락, 귀, 쓰고 있는 모자도 함께 커집니다. 손바닥만, 가슴만처럼 그 부분만 바꿀 수도 있습니다(Modular Avatar의 Scale Adjuster).

```text
시점이 낮으니 고쳐 줘. 머리를 조금 크게 해 줘
```

적용 전후를 나란히 놓은 이미지에 시점 위치를 빨간 표시로 보여 준 뒤 적용합니다. 「BigHead를 되돌려 줘」라고 하면 되돌립니다.

### 표정 바꾸기

핸드 제스처의 표정을 바꾸거나, 메뉴에서 표정을 골라 고정하거나, 볼 홍조·눈물·땀 같은 셰이프 키를 켜고 끌 수 있습니다. 아바타의 애니메이터는 바꾸지 않고 표정용 레이어를 추가합니다(Modular Avatar).

```text
오른손 주먹을 웃는 얼굴로 해 줘. 메뉴에서 게슴츠레한 눈으로 고정할 수 있게 해 줘
```

에이전트는 얼굴의 셰이프 키와 아바타에 처음부터 들어 있는 제스처 표정(어느 손의 어떤 제스처에서 어떤 셰이프 키가 움직이는지)을 조사한 뒤 레시피를 보여 주고, 표정마다 얼굴 이미지로 확인을 받은 뒤 적용합니다. 제작자의 표정은 남고, 레시피에 적은 셰이프 키만 덮어씁니다. 「Face 표정을 떼 줘」라고 하면 뗍니다.

### 아바타 업데이트에 개변 이어 가기

제작자가 아바타를 업데이트했을 때, 이 플러그인으로 넣은 개변(의상 토글, 색상 바리에이션, 체형, 소품, 흔들리는 부분, 시점과 크기, 표정)을 새 버전에 다시 적용합니다.

```text
Salt를 새 버전으로 바꿨으니 개변을 이어 가 줘. 새 버전은 Assets/DSHTest/SaltV2.unity에 두었어
```

에이전트는 지금 아바타에 걸린 개변과 손으로 바꾼 값(Inspector에서 고친 값 등)을 목록으로 보여 줍니다. 이어서 새 버전을 조사해 개변마다 사용하는 메시, 셰이프 키, 본이 있는지 확인하고, 이름이 바뀐 것은 비슷한 후보를 보여 줍니다. 준비된 개변은 한 번 확인한 뒤 한꺼번에 다시 적용합니다. 손으로 바꾼 값은 자동으로 복사하지 않고, 다시 할 항목의 목록으로 보여 줍니다.

### 퍼포먼스 랭크 조사

「퍼포먼스 랭크를 조사해 줘」라고 요청하면 PC와 Mobile의 퍼포먼스 랭크, 랭크를 정하는 항목(예: 스킨드 메시 수), 한 단계 위의 랭크로 만들기 위한 기준을 보여 줍니다. 빌드 전의 원래 prefab으로 센 기준이므로, 최종 랭크는 VRChat SDK의 빌드 화면에서 확인해 주세요.

「파라미터가 몇 bit 남았어?」라고 하면 동기화되는 파라미터 사용량(상한 256 bit)을 VRCFury나 Modular Avatar가 빌드 때 추가하는 분량까지 포함해 셉니다. 측정한 뒤에는 의상 토글이나 소품을 추가하기 전에 남은 양이 표시되고, 상한을 넘는 변경은 적용 전에 멈춥니다.

## 안전 장치와 되돌리는 방법

- **처음에는 읽기만**: 구성을 조사하는 단계에서는 프로젝트의 파일을 읽기만 합니다. Unity 실행과 Git 기록은 개변을 적용할 때 합니다.
- **적용 전에 확인**: 에이전트는 대상, 변경 예정, 만들어질 파일을 보여 준 뒤 적용합니다. 확인한 뒤에 씬이나 레시피가 바뀌면 다시 확인을 받습니다.
- **Git 복원 지점**: 처음 Git을 쓰는 프로젝트에서는 PC에 복원 지점을 만드는 순서가 안내됩니다. 이미 Git으로 관리하는 프로젝트에 기록하지 않은 변경이 있으면 먼저 기록하도록 요청합니다.
- **Unity는 닫아 두기**: 적용과 촬영에서는 Unity를 따로 실행해 작업합니다. 대상 프로젝트를 열고 있는 Unity는 씬을 저장하고 닫아 주세요.
- **움직임을 확인한 뒤 보여 주기**: 표정, 메뉴, 소품의 「내려놓기」는 VRChat과 같은 방식으로 빌드한 아바타를 제스처와 메뉴로 움직여 확인합니다(Gesture Manager 대신). 흔들리는 부분은 Unity의 Play 모드에서 아바타를 흔들고 걷고 앉게 해서 흔들림과 다리에 파고드는 깊이를 잽니다. 「더 부드럽게」「다리를 뚫지 않게」 같은 요청은 목표에 닿을 때까지 값과 콜라이더를 조금씩 바꿔 시험하고, 결과를 보여 준 뒤 적용합니다. 흔들림이나 1인칭 시점 같은 최종 확인은 부탁드립니다.
- **실패하면 원래 상태로**: Unity에서 저장한 뒤의 확인에 실패하면 씬을 실행 전 상태로 되돌립니다.
- **이어서 개변 가능**: 이 플러그인으로 저장하고 확인한 씬은, 직접 변경하기 전까지는 Git에 다시 기록하지 않고 이어서 개변할 수 있습니다.

이 플러그인으로 한 변경은 다음처럼 요청하면 되돌릴 수 있습니다. 떼기 전에 무엇을 되돌릴지 확인합니다.

| 되돌리고 싶은 것 | 요청 예 |
| --- | --- |
| 의상 토글 | 「후드티 토글을 떼 줘」 |
| 색상 바리에이션, lilToon 조정 | 「Hoodie_Blue 색상 바리에이션을 삭제해 줘」 |
| 체형 조정 | 「Fit_Hoodie 체형 조정을 되돌려 줘」 |
| 소품, 머리카락 | 「WolfHair를 떼 줘」 |
| 흔들림 조정 | 「SoftHair 흔들림 조정을 되돌려 줘」 |
| 시점, 부분 크기 | 「BigHead를 되돌려 줘」 |
| 표정 | 「Face 표정을 떼 줘」 |

그 밖의 변경은 Git 복원 지점에서 씬을 되돌립니다. 방법은 채팅으로 물어봐 주세요.

## 동작 확인 환경

| 항목 | DSH | Claude Code |
| --- | --- | --- |
| 앱 | DeepSeek Harness Desktop(Windows) | Claude 데스크톱 앱 |
| 모델 | DeepSeek V4.1 Flash(화면 표시 예 `DeepSeek-V41-Flash`) | Opus 5.5 |
| 에포트(추론 강도) | `MAX` | 중간 이상 |

위 이외의 조합에서의 동작은 확인하지 않았습니다. Codex 버전은 아직 동작을 확인하지 않았습니다.

## 문제가 생겼을 때

- **VRChat Avatar가 표시되지 않습니다.** Plugins에서 플러그인이 설치되어 있는지 확인하고, DSH에서 새 세션을 만듭니다.
- **Claude Code에서 스킬이 사용되지 않습니다.** 데스크톱 앱에서는 **+** → **Plugins** → **Manage plugins**, 터미널 버전에서는 `/plugin`으로 `dsh-vrc-unity-supporter`가 활성화되어 있는지 확인합니다. 그다음 새 세션을 시작합니다(터미널 버전은 `/reload-plugins`로도 가능).
- **`claude`를 찾을 수 없다고 표시됩니다.** [Claude Code 설치](https://code.claude.com/docs/en/setup)의 Windows용 순서로 `claude` 명령을 설치하고 PowerShell을 다시 엽니다.
- **Codex에서 스킬이 사용되지 않습니다.** Codex 앱의 **Plugins**에서 **VRChat Avatar (Unity)** 플러그인이 설치되어 있는지 확인하고 새 스레드를 시작합니다. 최신 버전으로 하려면 `codex plugin marketplace upgrade dsh-vrc-unity-supporter`를 실행합니다.
- **Codex에서 Unity 실행이 도중에 멈춥니다.** 첫 컴파일에는 몇 분이 걸립니다. Unity가 아직 동작 중일 수 있으니, 채팅에서 「Unity가 아직 동작 중인지 확인해 줘」라고 요청한 뒤 다시 요청해 주세요.
- **프로젝트를 찾을 수 없습니다.** 사용하는 앱에서 열고 있는 폴더에 `Assets`와 `ProjectSettings`가 있는지 확인합니다.
- **「Blender was not found」라고 표시됩니다.** Blender를 설치하고 사용하는 앱을 다시 엽니다. 다른 위치에 설치했다면 환경 변수 `DSH_BLENDER`에 `blender.exe`의 전체 경로를 설정합니다.
- **색상 바리에이션에서 「PhotoCraft CLI was not found」라고 표시됩니다.** PhotoCraft를 설치하고 사용하는 앱을 다시 엽니다. 다른 위치에 설치했다면 환경 변수 `PHOTOCRAFT_CLI`에 `photocraft-cli.exe`의 전체 경로를 설정합니다.
- **촬영(개변 전후 이미지)이 실패합니다.** 촬영에서는 GPU를 사용해 Unity를 실행합니다. Unity를 닫고 다시 요청하고, 그래도 실패하면 채팅에 표시된 로그 위치를 확인해 주세요.
- **체형 조정을 되돌릴 수 없습니다.** 0.10.0 이전에 적용한 체형 조정에는 되돌리기 위한 기록이 없습니다. Git 복원 지점에서 씬을 되돌려 주세요.
- **Git 이름이나 이메일 주소를 요구받았습니다.** 채팅에서 「이 프로젝트에서 Git 이름과 이메일 주소를 설정하는 방법을 알려 줘」라고 물어봐 주세요.
- **설치 프로그램이 도중에 멈춥니다.** DSH를 작업 표시줄 알림 영역에서도 종료하고, 화면에 표시된 오류를 확인해 주세요. [설치 프로그램 문제 해결(일본어)](installer/README.md#うまくいかないとき)
- **플러그인이 0.2.0 그대로입니다.** 최신 버전으로 업데이트해 주세요. 0.2.0에서는 Editor 스크립트의 초기 배치를 직접 해야 합니다. [0.2.0 설정 순서(일본어)](https://github.com/mistraparutenaste/dsh-vrc-unity-supporter/blob/v0.2.0/README.md#プロジェクトへの初期配置)

<details>
<summary>메인테이너용 테스트와 공개 순서</summary>

Windows에서 `python -B -m unittest discover -s tests -v`를 실행하면 읽기, 의상 토글, 색상 바리에이션, 체형, 소품, Blender CLI의 회귀 테스트를 실행할 수 있습니다(Unity, Blender, PhotoCraft는 가짜를 사용하므로 필요 없습니다). Unity 2022.3.22f1이 설치된 PC에서는 `templates/Editor/`의 헬퍼를 Unity의 DLL로 컴파일하는 테스트도 동작합니다(없는 PC에서는 skip). GitHub에서는 push와 PR마다 `.github/workflows/ci.yml`이 Windows와 Python 3.10 / 3.13에서 같은 테스트와 `verify-package.ps1`을 실행합니다. Claude Code 버전의 매니페스트는 `claude plugin validate . --strict`로 확인할 수 있습니다. 버전을 올릴 때는 `package.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`을 맞춥니다(`verify-package.ps1`이 대조합니다). Codex 버전은 매니페스트가 `.codex-plugin/plugin.json`, 마켓플레이스가 `.agents/plugins/marketplace.json`, 입구 스킬이 `codex/skills/vrc-avatar/`입니다. 공유 스킬은 `skills/`에 있고, Claude Code용 입구 스킬(`claude/skills/vrc-avatar/`)과 Codex용 입구 스킬은 모두 전체 스킬로 안내합니다. BOOTH에서 배포하는 ZIP은 커밋한 뒤 `powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-booth.ps1`로 `dist/booth/`에 만듭니다(ZIP 안의 설명은 `booth/00_README_JA.txt`, 상품 페이지 초안은 `booth/LISTING.md`). 자신의 Editor 스크립트를 사용할 때는 `templates/Editor/`의 헬퍼를 `Assets/DSH/Editor/`에 배치합니다. `templates/AGENTS.template.md`는 선택 사항인 프로젝트 메모입니다.

```powershell
npm login
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1
```

`publish.ps1`은 다음을 순서대로 실행하며, 전제 조건이 빠져 있으면 **아무것도 망가뜨리지 않고 멈춥니다**.

1. `verify-package.ps1`(BOM / 스킬 이름 / JSON / `dsh.bundle.patch` / 플러그인 매니페스트)
2. `npm pack --dry-run`으로 포함된 내용 확인
3. npm / gh 인증 확인(로그인하지 않았다면 실행할 명령을 표시하고 종료)
4. `npm publish --access public`(같은 버전이 이미 있으면 skip. 2단계 인증을 쓰지 않는 경우 `-Token`에 npm 토큰을 전달)
5. `gh repo create ... --push`, `git tag`, 태그 push

`-DryRun`을 붙이면 4 이후를 실행하지 않고, 무엇을 할지만 표시합니다.

</details>

## 라이선스

MIT. 서드파티의 취급은 [THIRD-PARTY.md](THIRD-PARTY.md)를 참조해 주세요.
이 패키지는 VRChat Inc. / Unity Technologies / 각 VPM 패키지 작자와는 관계가 없습니다.
