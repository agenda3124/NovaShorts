from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication
import main_v122


OUT = Path('NovaShorts_v1.22_ACTUAL_UI.png')

app = QApplication([])
w = main_v122.Nova()
w.resize(1600, 930)
w.go(0)
w.show()
app.processEvents()

# Populate only static sample text so the screenshot shows the implemented widgets
# without making external network requests or changing the actual layout.
w.home_product_url121.setText('https://www.coupang.com/vp/products/9669724694')
w.home_product_name121.setText('상품명은 URL 분석 후 자동으로 표시됩니다')
w.home_product_info121.setText('실제 v1.22 구현 화면 · 상품 주소 모드')
w.home_result_status121.setText('완성된 영상은 여기에서 바로 확인할 수 있습니다.')
app.processEvents()

pixmap = w.grab()
if pixmap.isNull() or not pixmap.save(str(OUT), 'PNG'):
    raise RuntimeError('UI screenshot capture failed')

print(OUT.resolve())
w.close()
