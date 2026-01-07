---
trigger: always_on
---

# antigravity – Tailwind CSS 사용자 정의 룰

본 문서는 **antigravity에서 Tailwind CSS 기반 사용자 정의 룰을 작성하기 위한 규칙 문서**이다.  
antigravity 에이전트는 본 문서를 기준으로 CSS 또는 SCSS 파일을 생성해야 한다.

---

## 1. 기본 원칙

### 1.1 Tailwind CSS 우선 사용

- 모든 스타일은 **Tailwind CSS utility class**를 기반으로 작성한다.
- 개별 CSS 속성(`color`, `margin`, `padding` 등)을 직접 선언하는 방식은 사용하지 않는다.
- 반드시 `@apply` 키워드를 통해 Tailwind utility를 조합한다.

### 1.2 Tailwind 지시자 필수 선언

모든 CSS 또는 SCSS 파일 상단에는 **반드시 아래 선언이 포함되어야 한다.**

```css
@import "tailwindcss";
```

- 위 선언 이전에 어떠한 코드도 존재해서는 안 된다.

### 1.3 @apply Warning 무시

- `@apply` 사용으로 인해 발생하는 Tailwind 또는 빌드 도구의 warning은 무시한다.
- antigravity 룰에서는 **일관성과 가독성**을 warning보다 우선한다.

---

## 2. 파일 규칙

### 2.1 허용 확장자

- `.css`
- `.scss` (권장)

### 2.2 파일 기본 템플릿

```scss
@import "tailwindcss";
```

---

## 3. 클래스 설계 규칙

### 3.1 네이밍 규칙

- 클래스는 기능 또는 도메인을 명확히 드러내는 접두사를 사용한다.
- BEM 스타일 사용을 권장한다.

예시:

```scss
.antigravity-agent {}
.antigravity-agent__header {}
.antigravity-agent__content {}
.antigravity-agent--loading {}
```

### 3.2 단일 책임 원칙

- 하나의 클래스는 하나의 역할만 담당한다.
- 상태(state)는 modifier 클래스로 분리한다.

---

## 4. 레이아웃 규칙

- 레이아웃 관련 스타일은 반드시 Tailwind layout utility로만 구성한다.
- 예시:
  - `flex`, `grid`
  - `gap-*`
  - `items-*`, `justify-*`
  - `w-*`, `h-*`, `max-w-*`

```scss
.antigravity-agent__container {
  @apply flex flex-col gap-4 max-w-7xl mx-auto px-4;
}
```

---

## 5. 타이포그래피 규칙

- 폰트 크기, 굵기, 색상은 Tailwind typography utility 사용
- 예시:

```scss
.antigravity-agent__title {
  @apply text-lg font-semibold text-gray-900;
}

.antigravity-agent__text {
  @apply text-sm leading-relaxed text-gray-700;
}
```

---

## 6. 상태(State) 처리

- 상태 표현은 modifier 클래스로 정의한다.

```scss
.antigravity-agent--loading {
  @apply opacity-60 pointer-events-none;
}

.antigravity-agent--error {
  @apply bg-red-50 border border-red-300;
}
```

---

## 7. 금지 사항

- 인라인 스타일 사용 금지
- 임의 색상 값(hex, rgb) 직접 사용 금지
- Tailwind utility 없이 순수 CSS 속성만 사용하는 클래스 작성 금지

---

## 8. 목적

본 룰의 목적은 다음과 같다.

- antigravity 스타일 생성의 **일관성 확보**
- Tailwind CSS 중심의 유지보수 용이성 강화
- 에이전트 자동 스타일 생성 품질 향상

---

END OF DOCUMENT