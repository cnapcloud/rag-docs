#!/usr/bin/env bash
#
# optimize-video.sh
# mp4 파일을 웹 스트리밍에 최적화된 형태로 재인코딩한다.
# (H.264 + AAC + faststart, 필요 시 최대 해상도/CRF 조절 가능)
#
# 사용법:
#   ./optimize-video.sh <입력.mp4> [출력.mp4] [crf] [max_height]
#
# 예시:
#   ./optimize-video.sh rag-demo.mp4
#       -> rag-demo.mp4 를 rag-demo-optimized.mp4 로 저장 (crf 23, 원본 해상도 유지)
#
#   ./optimize-video.sh rag-demo.mp4 rag-demo.mp4
#       -> 같은 이름으로 덮어쓰기 (임시 파일 사용 후 교체, 원본 보존 안 함)
#
#   ./optimize-video.sh rag-demo.mp4 rag-demo-optimized.mp4 20 1080
#       -> crf 20, 최대 세로 1080px로 축소
#
#   디렉터리 전체 일괄 처리:
#   for f in static/img/video/*.mp4; do ./optimize-video.sh "$f"; done

set -euo pipefail

INPUT="${1:-}"
OUTPUT="${2:-}"
CRF="${3:-23}"
MAX_HEIGHT="${4:-}"   # 비워두면 원본 해상도 유지

if [[ -z "$INPUT" ]]; then
  echo "사용법: $0 <입력.mp4> [출력.mp4] [crf] [max_height]" >&2
  exit 1
fi

if [[ ! -f "$INPUT" ]]; then
  echo "오류: 입력 파일을 찾을 수 없습니다 -> $INPUT" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "오류: ffmpeg가 설치되어 있지 않습니다. (macOS: brew install ffmpeg)" >&2
  exit 1
fi

DIR="$(dirname "$INPUT")"
BASE="$(basename "$INPUT")"
NAME="${BASE%.*}"

# 출력 경로 기본값 처리
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${DIR}/${NAME}-optimized.mp4"
fi

# 같은 파일로 덮어쓰는 경우: 임시 파일에 쓴 뒤 교체 (ffmpeg는 입출력 동일 파일 불가)
OVERWRITE_IN_PLACE=false
if [[ "$(cd "$DIR" && pwd)/$(basename "$OUTPUT")" == "$(cd "$DIR" && pwd)/${BASE}" ]]; then
  OVERWRITE_IN_PLACE=true
  TMP_OUTPUT="${DIR}/.${NAME}.tmp.mp4"
else
  TMP_OUTPUT="$OUTPUT"
fi

# 스케일 필터 구성 (max_height 지정 시에만, 세로 기준 비율 유지, 짝수 보정)
SCALE_ARGS=()
if [[ -n "$MAX_HEIGHT" ]]; then
  SCALE_ARGS=(-vf "scale=-2:'min(${MAX_HEIGHT},ih)'")
fi

echo "▶ 처리 중: $INPUT"
echo "  - CRF: $CRF"
[[ -n "$MAX_HEIGHT" ]] && echo "  - 최대 세로 해상도: ${MAX_HEIGHT}px"
echo "  - 출력: $OUTPUT"

# eval 없이 배열로 안전하게 실행
if [[ -n "$MAX_HEIGHT" ]]; then
  ffmpeg -y -i "$INPUT" \
    -vf "scale=-2:'min(${MAX_HEIGHT},ih)'" \
    -c:v libx264 -crf "$CRF" -preset slow \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$TMP_OUTPUT"
else
  ffmpeg -y -i "$INPUT" \
    -c:v libx264 -crf "$CRF" -preset slow \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$TMP_OUTPUT"
fi

if [[ "$OVERWRITE_IN_PLACE" == true ]]; then
  mv "$TMP_OUTPUT" "$OUTPUT"
fi

# 결과 비교 출력
ORIG_SIZE=$(du -h "$INPUT" | cut -f1)
NEW_SIZE=$(du -h "$OUTPUT" | cut -f1)

echo ""
echo "완료"
echo "원본: $INPUT ($ORIG_SIZE)"
echo "결과: $OUTPUT ($NEW_SIZE)"