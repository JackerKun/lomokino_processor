"""Name source launches before Qt creates the native application menu."""

from ctypes import CDLL, c_char_p, c_uint32, c_void_p


def set_source_app_name(name):
    core = CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    core.CFBundleGetMainBundle.restype = c_void_p
    core.CFBundleGetInfoDictionary.argtypes = [c_void_p]
    core.CFBundleGetInfoDictionary.restype = c_void_p
    core.CFStringCreateWithCString.argtypes = [c_void_p, c_char_p, c_uint32]
    core.CFStringCreateWithCString.restype = c_void_p
    core.CFDictionarySetValue.argtypes = [c_void_p, c_void_p, c_void_p]
    core.CFDictionarySetValue.restype = None
    core.CFRelease.argtypes = [c_void_p]
    core.CFRelease.restype = None

    bundle = core.CFBundleGetMainBundle()
    info = core.CFBundleGetInfoDictionary(bundle) if bundle else None
    if not info:
        return

    # Change the bundle dictionary in this process before Cocoa registers the app.
    utf8_encoding = 0x08000100
    app_name = core.CFStringCreateWithCString(None, name.encode('utf-8'), utf8_encoding)
    try:
        for field in (b'CFBundleName', b'CFBundleDisplayName'):
            key = core.CFStringCreateWithCString(None, field, utf8_encoding)
            try:
                core.CFDictionarySetValue(info, key, app_name)
            finally:
                core.CFRelease(key)
    finally:
        core.CFRelease(app_name)
