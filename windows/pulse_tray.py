"""Own Win32 notification icon. No hooks, screen reading or external dependencies."""
import ctypes as c
from ctypes import wintypes as w
import os
import sys


class Tray:
    MESSAGE = 0x8014

    def __init__(self, root, toggle, menu, unavailable):
        self.root = root
        self.toggle = toggle
        self.menu = menu
        self.unavailable = unavailable
        self.available = False
        self.closed = False
        self.hwnd = None
        if sys.platform != 'win32':
            return
        self.user = c.WinDLL('user32', use_last_error=True)
        self.shell = c.WinDLL('shell32', use_last_error=True)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        callback = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)

        class WindowClass(c.Structure):
            _fields_ = [('style', w.UINT), ('proc', callback), ('classExtra', c.c_int),
                        ('windowExtra', c.c_int), ('instance', w.HINSTANCE),
                        ('icon', w.HICON), ('cursor', w.HANDLE), ('background', w.HBRUSH),
                        ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]

        class IconData(c.Structure):
            _fields_ = [('size', w.DWORD), ('hwnd', w.HWND), ('id', w.UINT),
                        ('flags', w.UINT), ('message', w.UINT), ('icon', w.HICON),
                        ('tip', w.WCHAR * 128), ('state', w.DWORD), ('mask', w.DWORD),
                        ('info', w.WCHAR * 256), ('version', w.UINT),
                        ('infoTitle', w.WCHAR * 64), ('infoFlags', w.DWORD),
                        ('guid', c.c_ubyte * 16), ('balloonIcon', w.HICON)]

        def signature(dll, name, result, *args):
            f = getattr(dll, name); f.restype = result; f.argtypes = args
            return f

        signature(kernel, 'GetModuleHandleW', w.HMODULE, w.LPCWSTR)
        signature(self.user, 'RegisterClassW', w.WORD, c.POINTER(WindowClass))
        signature(self.user, 'UnregisterClassW', w.BOOL, w.LPCWSTR, w.HINSTANCE)
        signature(self.user, 'CreateWindowExW', w.HWND, w.DWORD, w.LPCWSTR, w.LPCWSTR,
                  w.DWORD, c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p)
        signature(self.user, 'DefWindowProcW', c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        signature(self.user, 'DestroyWindow', w.BOOL, w.HWND)
        signature(self.user, 'LoadIconW', w.HICON, w.HINSTANCE, c.c_void_p)
        signature(self.user, 'RegisterWindowMessageW', w.UINT, w.LPCWSTR)
        signature(self.user, 'PeekMessageW', w.BOOL, c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT)
        signature(self.user, 'DispatchMessageW', c.c_ssize_t, c.POINTER(w.MSG))
        signature(self.user, 'SendMessageW', c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
        signature(self.shell, 'Shell_NotifyIconW', w.BOOL, w.DWORD, c.POINTER(IconData))
        self.instance = kernel.GetModuleHandleW(None)
        self.class_name = 'AgentPulseTray' + str(os.getpid())
        self.restart = self.user.RegisterWindowMessageW('TaskbarCreated')

        @callback
        def procedure(hwnd, message, wp, lp):
            if message == self.MESSAGE:
                if lp in (0x202, 0x400): self.root.after(0, self.toggle)
                elif lp in (0x205, 0x7b): self.root.after(0, self.menu)
                return 0
            if message == self.restart:
                self.root.after(0, self.restore)
                return 0
            return self.user.DefWindowProcW(hwnd, message, wp, lp)

        self.procedure = procedure  # Native callback must outlive its HWND.
        wc = WindowClass(); wc.proc = procedure; wc.instance = self.instance; wc.name = self.class_name
        if not self.user.RegisterClassW(c.byref(wc)):
            raise OSError(c.get_last_error(), 'Cannot register own tray window')
        # Hidden top-level window receives Explorer's TaskbarCreated broadcast.
        self.hwnd = self.user.CreateWindowExW(0, self.class_name, 'Agent Pulse', 0,
                                             0, 0, 0, 0, None, None, self.instance, None)
        if not self.hwnd:
            self.close(); raise OSError(c.get_last_error(), 'Cannot create own tray window')
        self.data = IconData(); self.data.size = c.sizeof(IconData)
        self.data.hwnd = self.hwnd; self.data.id = 1; self.data.flags = 1 | 2 | 4
        self.data.message = self.MESSAGE; self.data.icon = self.user.LoadIconW(None, c.c_void_p(32512))
        self.data.tip = 'Agent Pulse'
        self.restore(); self.pump()

    def restore(self):
        if self.closed or not self.hwnd: return
        self.shell.Shell_NotifyIconW(2, c.byref(self.data))
        self.available = bool(self.shell.Shell_NotifyIconW(0, c.byref(self.data)))
        if self.available:
            # Version zero deliberately uses un-packed legacy mouse notifications.
            self.data.version = 0
            self.shell.Shell_NotifyIconW(4, c.byref(self.data))
        else:
            self.unavailable()

    def update(self, text):
        if self.closed or not self.hwnd: return
        self.data.tip = text[:127]
        if not self.shell.Shell_NotifyIconW(1, c.byref(self.data)): self.restore()

    def pump(self):
        if self.closed: return
        message = w.MSG()
        # Read only messages for our own HWND; never intercept another application.
        while self.user.PeekMessageW(c.byref(message), self.hwnd, 0, 0, 1):
            self.user.DispatchMessageW(c.byref(message))
        self.root.after(50, self.pump)

    def close(self):
        self.closed = True
        if self.hwnd:
            if hasattr(self, 'data'): self.shell.Shell_NotifyIconW(2, c.byref(self.data))
            self.user.DestroyWindow(self.hwnd); self.hwnd = None
        if hasattr(self, 'class_name'): self.user.UnregisterClassW(self.class_name, self.instance)
        self.available = False
