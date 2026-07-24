.PHONY: install record record-namuwiki convert

install:
	uv sync
	uv run playwright install chromium

record:
	uv run python record.py

record-namuwiki:
	uv run python record-namuwiki.py

# webm -> QuickTime-playable mp4 (H.264). Requires system ffmpeg
# (brew install ffmpeg) - the Playwright-bundled ffmpeg has no libx264.
convert:
	ffmpeg -y -i "$$(ls -t output/*.webm | head -1)" \
		-c:v libx264 -pix_fmt yuv420p -movflags +faststart \
		output/demo.mp4
