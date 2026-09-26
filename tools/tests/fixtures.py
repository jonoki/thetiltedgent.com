"""Shared by the tools tests: tools/ on the import path, and a small, made-up report page.

Each test feeds a small, made-up page or record to one parser, so a change to the report markup rules shows up
here before it shows up as a wrong tag or a failed gate on the live library.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # tools/

PAGE = """<!DOCTYPE html>
<html lang="en"><head><title>ACME — Acme Widgets Inc. | Stock Analysis</title><style>body{}</style></head>
<body>
<div class="price-current">$1,234.50</div>
<p>Static data as of September 10, 2026 (market close). HQ: Springfield, Illinois</p>
<table class="fin-table"><tbody>
<tr><td>Trailing P/E</td><td>24.1x</td></tr>
<tr><td>EPS (TTM)</td><td>$51.22</td></tr>
<tr><td>52-Week Range</td><td>$1,001.00 &ndash; $1,300.00</td></tr>
</tbody></table>
<canvas></canvas><canvas></canvas>
<script>const labels = ['Sep \\'21', "Oct '21", `Nov 21`]; const prices = [1100.5,1200,1234.5];</script>
</body></html>
"""
