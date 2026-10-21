"""Explicit owner click for one reviewed manifest; no network or credential APIs."""
import ctypes
import sys

def confirm_publication(plan, show=None):
    if sys.platform != 'win32' or not sys.stdin.isatty(): raise RuntimeError('Windowsの本人端末が必要です')
    if show is None:
        show=ctypes.WinDLL('user32',use_last_error=True).MessageBoxW
        show.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_uint];show.restype=ctypes.c_int
    message=(f"{plan['title']}\n\n送信先: ippon.sakura.ne.jp / ippon\n公開先: /home/ippon/www\n"
             f"記事: {plan['files'][-3]['path']}\n対象: {len(plan['files'])}ファイル\n\n"
             '一致する既存ファイルは送らず、未知の内容は停止します。\n'
             '既存対象を別の実行フォルダへバックアップします。\n'
             '画像と記事の公開を確認してから年間一覧・TOPを更新します。\n\n'
             '「はい」で今回だけ送信。「いいえ」で終了。登録済み資格情報を利用します。\n'
             '未登録ならこの端末で非表示入力を求めます。')
    if plan.get('operation') == 'correction':
        message = (f"{plan['title']}\n\n"
                   f"https://ippon.sakura.ne.jp/{plan['files'][-3]['path']}\n"
                   f"{len(plan['files'])} files checked; only the article HTML may change.\n"
                   "Existing image and navigation files must already match.\n"
                   "All existing files are backed up before the article update.\n\n"
                   "Yes runs the reviewed correction. No cancels without authentication or upload.")
        return show(None,message,'Reviewed article correction',0x4|0x20|0x100|0x10000)==6
    return show(None,message,'今回の例会報告を公開しますか',0x4|0x20|0x100|0x10000)==6
