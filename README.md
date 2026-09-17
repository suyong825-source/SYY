# andopt — 안드로이드 최적화 도구

ADB로 연결된 안드로이드 기기를 진단하고 최적화하는 커맨드라인 도구입니다.
루팅이 필요 없으며, 되돌릴 수 없는 작업은 하지 않습니다.

## 준비

1. [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)를 설치하고 `adb`를 PATH에 추가합니다.
2. 기기에서 **개발자 옵션 → USB 디버깅**을 켭니다.
3. 케이블로 연결한 뒤 기기 화면의 디버깅 승인 팝업에서 허용합니다.

```bash
pip install -e .
andopt devices   # 연결 확인
```

## 사용법

```bash
andopt report              # 기기/저장공간/메모리/배터리 종합 진단
andopt storage             # 저장공간 사용량
andopt battery             # 배터리 잔량·온도·건강도
andopt memory              # 메모리 사용량
andopt apps                # 설치된 사용자 앱 목록과 활성/비활성 상태

andopt clean               # 모든 앱의 캐시 정리 (사용자 데이터는 보존)
andopt clean com.example.a # 특정 앱만 캐시 정리

andopt bloat               # 비활성화 후보인 선탑재 앱 확인 (변경 없음)
andopt bloat --disable     # 확인 후 후보를 비활성화
andopt disable com.foo.bar # 특정 패키지 비활성화
andopt enable  com.foo.bar # 되돌리기
```

기기가 여러 대 연결되어 있으면 `--serial`로 지정합니다. `-y`는 확인 프롬프트를 건너뜁니다.

```bash
andopt --serial ABC123 -y clean
```

## 안전성

- **캐시 정리**는 `pm trim-caches` / `pm clear --cache-only`만 사용합니다. 앱 데이터, 로그인 상태, 사진은 삭제되지 않습니다.
- **비활성화**는 `pm disable-user --user 0`을 사용합니다. 앱을 제거하지 않으므로 `andopt enable`로 언제든 되돌릴 수 있고, 공장 초기화 시에도 복구됩니다.
- 비활성화 후보 목록(`KNOWN_BLOAT`)에는 통신·카메라·설정 같은 핵심 시스템 구성요소를 넣지 않습니다. 목록은 `andopt/commands/apps.py`에 있습니다.
- 파괴적 명령은 실행 전 항상 확인을 요청합니다.

## 개발

```bash
pip install -e ".[dev]"
pytest
```

기기 출력 파싱은 `andopt/parse.py`의 순수 함수로 분리되어 있어, 실제 기기 없이도 테스트할 수 있습니다.
