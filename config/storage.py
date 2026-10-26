from whitenoise.storage import CompressedManifestStaticFilesStorage


class Storage(CompressedManifestStaticFilesStorage):
    # Rewrite `import ... from "./cards.js"` to the hashed name too, so every
    # page shares one module instance and caches bust correctly.
    support_js_module_import_aggregation = True
