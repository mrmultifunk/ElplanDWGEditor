from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import core_logic as core
from elplan_core.platform import printing


def test_printing_rejects_non_windows_before_importing_pywin32():
    with patch.object(printing, "os", SimpleNamespace(name="posix")), patch.dict(
        sys.modules, {"pywintypes": None},
    ):
        try:
            core.print_vector_windows([], [])
        except RuntimeError as exc:
            assert "kun tilgængelig på Windows" in str(exc)
        else:
            raise AssertionError("Windows-print blev ikke afvist på en anden platform")


def test_printing_preserves_a3_landscape_and_cleans_up_the_print_job():
    con = SimpleNamespace(
        DMPAPER_A3=8, DMPAPER_A4=9, DMORIENT_LANDSCAPE=2, DMORIENT_PORTRAIT=1,
        DM_ORIENTATION=1, DM_PAPERSIZE=2, DM_COPIES=4, DM_OUT_BUFFER=8, DM_IN_BUFFER=16,
        LOGPIXELSX=1, LOGPIXELSY=2, HORZRES=3, VERTRES=4, PHYSICALWIDTH=5, PHYSICALHEIGHT=6,
        PS_SOLID=0, NULL_BRUSH=5, TRANSPARENT=1,
    )
    device_caps = {1: 300, 2: 300, 3: 4800, 4: 3400, 5: 4961, 6: 3508}
    driver = MagicMock()
    driver.GetPrinter.return_value = {"pPrintProcessor": "winprint"}
    driver.DocumentProperties.side_effect = [124, 1, 1]
    driver.GetDeviceCaps.side_effect = lambda _hdc, key: device_caps[key]
    gdi = MagicMock()
    gdi.GetTextExtentPoint32.return_value = (30, 10)
    mode = SimpleNamespace(Size=100, Fields=0)
    pywintypes = MagicMock()
    pywintypes.DEVMODEType.return_value = mode
    modules = dict(pywintypes=pywintypes, win32con=con, win32api=MagicMock(),
                   win32gui=gdi, win32print=driver)
    room = core.RoomPlacement(name="Køkken", points=[(0, 0), (400, 0), (400, 200)])
    cable = core.CablePlacement(
        points=[(0, 0), (400, 200)], cable_id="K-01", cable_spec="3G1,5", auto_label=True,
    )
    with patch.object(printing, "os", SimpleNamespace(name="nt")), patch.dict(sys.modules, modules):
        assert core.print_vector_windows(
            [], [], cables=[cable], rooms=[room], printer_name="Testprinter",
            paper="A3", orientation="Landskab", extents_override=(0, 0, 400, 200),
            fill_page=True,
        ) == "Testprinter"
    assert (mode.Fields, mode.PaperSize, mode.Orientation, mode.Copies) == (7, 8, 2, 1)
    pywintypes.DEVMODEType.assert_called_with(24)
    hdc = gdi.CreateDC.return_value
    driver.StartDoc.assert_called_once_with(hdc, ("Elplan", None, None, 0))
    driver.StartPage.assert_called_once_with(hdc)
    assert [call.args[-1] for call in gdi.TextOut.call_args_list] == ["Køkken", "K-01 · 3G1,5"]
    driver.EndPage.assert_called_once_with(hdc)
    driver.EndDoc.assert_called_once_with(hdc)
    driver.AbortDoc.assert_not_called()
    gdi.DeleteDC.assert_called_once_with(hdc)
    driver.ClosePrinter.assert_called_once_with(driver.OpenPrinter.return_value)
