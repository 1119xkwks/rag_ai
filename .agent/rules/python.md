---
trigger: always_on
---

# Python 프로젝트 코딩 규칙 (Java 개발자용 가이드)

본 프로젝트에서 파이썬 코드를 작성하거나 수정할 때 준수해야 할 규칙입니다. Java의 명시적인 스타일과 대비되는 파이썬의 특징을 주석으로 포함합니다.

## 1. 기본 구조 및 명명 규칙
* **Naming:** 변수와 함수명은 `snake_case`를 사용합니다. (Java의 camelCase와 다름)
* **Indentation:** 들여쓰기는 반드시 **4 Space**를 사용합니다. (파이썬은 중괄호 `{}` 대신 들여쓰기로 코드 블록을 구분함)

## 2. Java 개발자를 위한 문법 키워드 가이드 (코드 생성 시 반영)
코드 생성 시 다음 키워드와 주석 스타일을 적용하세요:

* **변수 선언:** 타입 명시 없이 바로 선언합니다.
  ```python
  items = []  # List 선언 (Java의 ArrayList 역할)
  user_info = {}  # Dictionary 선언 (Java의 HashMap 역할)