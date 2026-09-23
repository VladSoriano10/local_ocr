import time

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from local_ocr.gui import MainWindow


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "local_ocr.gui.QSettings",
        lambda *_: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_job(app, window, seconds=20):
    deadline = time.monotonic() + seconds
    while window.process is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert window.process is None, "El proceso GUI no terminó"
    app.processEvents()


def test_interface_scan_select_preview_export(app, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('local only')\n")
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "output"))
    window.root_edit.setText(str(project))
    window.start_scan()
    wait_job(app, window)
    assert window.scan_result is not None
    assert len(window.project_items) == 1
    item = window.project_items["main.py"]
    assert item.checkState(0) == Qt.CheckState.Checked
    window.preview_source(item, 0)
    assert "local only" in window.preview.toPlainText()
    window.check_all(False)
    assert not window.export_button.isEnabled()
    window.check_all(True)
    assert window.export_button.isEnabled()
    window.start_export()
    wait_job(app, window)
    assert window.last_output
    assert "1 archivos" in window.status.text()
    window.close()


def test_document_add_remove_and_mode(app, tmp_path):
    path = tmp_path / "test.pdf"
    path.write_bytes(b"not-used-for-processing")
    window = MainWindow()
    window.add_documents([str(path), str(path), "unknown.txt"])
    assert window.files.rowCount() == 1
    window.mode.setCurrentIndex(2)
    assert window.deskew.isEnabled()
    window.deskew.setChecked(True)
    window.mode.setCurrentIndex(0)
    assert not window.deskew.isChecked()
    window.clear_documents()
    assert window.files.rowCount() == 0
    window.close()


def test_gui_document_batch_continues_after_error(app, tmp_path):
    import pymupdf

    good = tmp_path / "good.pdf"
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a valid pdf")
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((50, 90), "Native PDF test")
        pdf.save(good)
    window = MainWindow()
    window.output_edit.setText(str(tmp_path / "output"))
    window.add_documents([str(bad), str(good)])
    window.start_documents()
    wait_job(app, window)
    assert window.files.item(0, 1).text() == "Error"
    assert window.files.item(1, 1).text() == "Listo"
    assert "1 error" in window.status.text()
    assert len(window.document_results) == 1
    assert "Native PDF test" in window.document_preview.toPlainText()
    assert window.pdf_button.isEnabled()
    window.copy_document_preview()
    assert "Native PDF test" in app.clipboard().text()
    window.files.setCurrentCell(0, 0)
    assert not window.document_preview.toPlainText()
    assert not window.pdf_button.isEnabled()
    window.files.selectRow(0)
    window.remove_documents()
    window.files.setCurrentCell(0, 0)
    assert "Native PDF test" in window.document_preview.toPlainText()
    window.close()
