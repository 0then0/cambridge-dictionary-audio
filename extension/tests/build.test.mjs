import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

for (const browser of ["chrome", "firefox"]) {
  test(`${browser} bundle contains only packaged modules, icons and notices`, async () => {
    const root = new URL(`../dist/${browser}/`, import.meta.url);
    const manifest = JSON.parse(await readFile(new URL("manifest.json", root), "utf8"));
    assert.equal(manifest.manifest_version, 3);
    assert.deepEqual(manifest.permissions, ["activeTab", "scripting", "downloads", "storage"]);
    assert.equal(manifest.host_permissions, undefined);
    assert.equal(manifest.content_scripts, undefined);
    assert.equal(manifest.background, undefined);
    assert.equal(manifest.action.default_popup, "popup.html");
    assert.match(manifest.content_security_policy.extension_pages, /script-src 'self'/);
    const files = await readdir(root);
    assert.ok(!files.includes("node_modules"));
    assert.ok(!files.includes("tests"));
    assert.ok(!files.some(file => file.endsWith(".ts")));
    for (const filename of ["main.js", "popup.js", "page.js", "settings.js", "popup.css", "popup.html", "LICENSE", "LICENSE-MIT", "NOTICE"]) {
      assert.ok((await readFile(new URL(filename, root))).length > 0);
    }
    for (const size of [16, 32, 48, 128]) {
      const png = await readFile(new URL(manifest.icons[size], root));
      assert.equal(png.readUInt32BE(16), size);
      assert.equal(png.readUInt32BE(20), size);
    }
    if (browser === "firefox") {
      assert.equal(manifest.browser_specific_settings.gecko.strict_min_version, "140.0");
      assert.deepEqual(manifest.browser_specific_settings.gecko.data_collection_permissions.required, ["none"]);
      assert.equal(manifest.browser_specific_settings.gecko_android.strict_min_version, "142.0");
    } else {
      assert.equal(manifest.browser_specific_settings, undefined);
    }
  });
}
