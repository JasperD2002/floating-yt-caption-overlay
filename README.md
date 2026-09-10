# floating-yt-caption-overlay
Sends YouTube closed captions to a local WebSocket server for overlay display.<br>
<br>
===========================================================================================<br>
<br>
Displays YouTube closed captions in a borderless, always-on-top, <br>
resizable overlay window with transparent background and text outline.<br>
<br>
Receives captions from a Chrome extension via WebSocket.<br>
<br>
Requirements:<br>
pip install websockets<br>
<br>
Setup:<br>
1. Load the extension in Chrome:<br>
Go to chrome://extensions<br>
Enable "Developer mode" (top-right)<br>
Click "Load unpacked" and select yt_caption_extension/<br>
2. Run this script:<br>
python yt_caption_overlay.py<br>
3. Play any YouTube video with CC enabled.<br>
<br>
Drag the overlay by clicking on the caption text.<br>
Resize by dragging the bottom-right corner handle.<br>
Right-click for options.<br>
