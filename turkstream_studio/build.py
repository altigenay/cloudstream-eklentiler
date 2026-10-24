"""Build step: turn an approved job into a `.cs3` package and a source archive.

CloudStream's own Gradle plugin does the packaging, so this module never
rewrites Kotlin that already exists. It only

1. validates the job contract (`review.json`, `spec.json`, `decisions.json`),
2. locates the plugin directory, or scaffolds one from the approved spec,
3. runs `./gradlew <Plugin>:make`,
4. copies the `.cs3` into the job and writes `status.json`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRADLE_TIMEOUT_SECONDS = 900


class BuildError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def class_name(slug: str) -> str:
    return "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]+", slug) if part) or "Provider"


def plugin_dirs(repo: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in repo.iterdir():
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        if (directory / "build.gradle.kts").is_file():
            found[directory.name.lower()] = directory
    return found


def resolve_plugin(repo: Path, slug: str, name: str) -> Path | None:
    existing = plugin_dirs(repo)
    for key in (slug.lower(), class_name(slug).lower()):
        if key in existing:
            return existing[key]
    for directory in existing.values():
        gradle = (directory / "build.gradle.kts").read_text(encoding="utf-8", errors="ignore")
        if name and name.lower() in gradle.lower():
            return directory
    return None


KOTLIN_TEMPLATE = '''package com.altigenay.{slug}

import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import org.jsoup.nodes.Element

class {cls}Provider : MainAPI() {{
    override var mainUrl = "{base_url}"
    override var name = "{name}"
    override var lang = "{language}"
    override val hasMainPage = true
    override var supportedTypes = setOf({types})
    override val hasDownloadSupport = false

    // Onaylanan mainPage sırası (studio: approve)
    override val mainPage = mainPageOf(
{main_page}
    )

    override suspend fun getMainPage(
        page: Int,
        request: MainPageRequest
    ): HomePageResponse {{
        // TODO(studio): bölüm seçicisini doğrula: {selector}
        val document = app.get(mainUrl).document
        val items = document.select("{selector}").mapNotNull {{ it.toSearchResult() }}
        if (items.isEmpty()) throw ErrorLoadingException("bölüm boş: ${{request.name}}")
        return newHomePageResponse(request.name, items)
    }}

    private fun Element.toSearchResult(): SearchResponse? {{
        val href = fixUrlNull(this.selectFirst("a[href]")?.attr("href")) ?: return null
        val title = this.selectFirst("h1, h2, h3, .title, [class*=title]")?.text()?.trim()
            ?: return null
        val image = this.selectFirst("img")
        val rawPoster = image?.attr("data-src")?.takeIf {{ it.isNotBlank() }} ?: image?.attr("src")
        val poster: String? = fixUrlNull(rawPoster)
        return newMovieSearchResponse(title, href, TvType.Movie) {{
            this.posterUrl = poster
        }}
    }}

    override suspend fun search(query: String): List<SearchResponse> {{
        // TODO(studio): sitenin arama isteğini (GET/POST + parametre) doğrula.
        val document = app.get("$mainUrl/?s=$query").document
        return document.select("{selector}").mapNotNull {{ it.toSearchResult() }}
    }}

    override suspend fun load(url: String): LoadResponse {{
        val document = app.get(url).document
        val title = document.selectFirst("h1")?.text()?.trim()
            ?: throw ErrorLoadingException("başlık bulunamadı")
        // TODO(studio): bölüm/kaynak düğümlerini gerçek sayfadan doğrula.
        return newMovieLoadResponse(title, url, TvType.Movie, url) {{
            this.posterUrl = fixUrlNull(document.selectFirst("meta[property=og:image]")?.attr("content"))
            this.plot = document.selectFirst("meta[name=description]")?.attr("content")
        }}
    }}

    override suspend fun loadLinks(
        data: String,
        isCastingPlaybackTypes: Boolean,
        subtitleCallback: (SubtitleFile) -> Unit,
        callback: (ExtractorLink) -> Unit
    ): Boolean {{
        // TODO(studio): iframe/player zincirini çöz; tek sunucu = tek kaynak.
        val document = app.get(data).document
        val source = document.selectFirst("iframe[src]")?.attr("src") ?: return false
        callback(
            newExtractorLink(
                this.name,
                this.name,
                fixUrl(source),
                ExtractorLinkType.VIDEO
            )
        )
        return true
    }}
}}
'''

PLUGIN_TEMPLATE = '''// Sürüm numarası: her değişiklikte bir artırın (CloudStream güncellemeyi buna bakarak görür)
version = 1

cloudstream {{
    description = "{description}"
    authors = listOf("altigenay")
    status = 1 // 1: çalışıyor, 2: deneniyor, 3: bozuk
    tvTypes = listOf({tv_types})
    language = "{language}"
    iconUrl = "{base_url}/favicon.ico"
}}
'''

MANIFEST_TEMPLATE = '''<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
</manifest>
'''


def scaffold(repo: Path, spec: dict, review: dict) -> Path:
    cls = class_name(spec["slug"])
    directory = repo / cls
    source_dir = directory / "src" / "main" / "kotlin" / "com" / "altigenay" / spec["slug"].replace("-", "")
    source_dir.mkdir(parents=True, exist_ok=True)
    (directory / "src" / "main").joinpath("AndroidManifest.xml").write_text(MANIFEST_TEMPLATE, encoding="utf-8")

    media = [section for section in review["sections"] if section.get("role") == "media"]
    main_page = "\n".join(
        f'        "{section.get("data") or section["id"]}" to "{section["title"]}",'
        for section in media
    ) or '        "main" to "Ana Sayfa",'
    selector = media[0]["selector"] if media else "article"

    (directory / "build.gradle.kts").write_text(
        PLUGIN_TEMPLATE.format(
            description=f'{spec["name"]} — studio tarafından üretilen iskelet',
            tv_types=", ".join(f'"{value}"' for value in spec["tvTypes"]),
            language=spec.get("language", "tr"),
            base_url=spec.get("baseUrl", ""),
        ),
        encoding="utf-8",
    )
    (source_dir / f"{cls}Provider.kt").write_text(
        KOTLIN_TEMPLATE.format(
            slug=spec["slug"].replace("-", ""),
            cls=cls,
            base_url=spec.get("baseUrl", ""),
            name=spec["name"],
            language=spec.get("language", "tr"),
            types=", ".join(f"TvType.{value}" for value in spec["tvTypes"]),
            main_page=main_page,
            selector=selector.replace('"', '\\"'),
        ),
        encoding="utf-8",
    )
    (source_dir / f"{cls}Plugin.kt").write_text(
        f'''package com.altigenay.{spec["slug"].replace("-", "")}

import com.lagradost.cloudstream3.plugins.CloudstreamPlugin
import com.lagradost.cloudstream3.plugins.Plugin
import android.content.Context

@CloudstreamPlugin
class {cls}Plugin : Plugin() {{
    override fun load(context: Context) {{
        registerMainAPI({cls}Provider())
    }}
}}
''',
        encoding="utf-8",
    )
    return directory


def gradle_command(repo: Path, plugin: Path) -> list[str]:
    wrapper = repo / "gradlew"
    if wrapper.is_file():
        return [str(wrapper), f"{plugin.name}:make"]
    raise BuildError(f"gradlew bulunamadı: {wrapper}")


def run_build(repo: Path, plugin: Path, log_path: Path) -> tuple[bool, str]:
    command = gradle_command(repo, plugin)
    try:
        result = subprocess.run(
            command,
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=GRADLE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        log_path.write_text(f"zaman aşımı: {GRADLE_TIMEOUT_SECONDS}s\n", encoding="utf-8")
        return False, "zaman aşımı"
    log_path.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    return result.returncode == 0, f"gradle çıkış kodu {result.returncode}"


def find_cs3(plugin: Path) -> Path | None:
    outputs = sorted(plugin.glob("build/*.cs3"), key=lambda path: path.stat().st_mtime, reverse=True)
    return outputs[0] if outputs else None


def zip_sources(plugin: Path, target: Path) -> Path:
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(plugin.rglob("*")):
            if not path.is_file() or "build" in path.parts or ".gradle" in path.parts:
                continue
            archive.write(path, f"{plugin.name}/{path.relative_to(plugin)}")
    return target


def build(job: Path, repo: Path | None = None, scaffold_missing: bool = True) -> dict:
    job = job.resolve()
    repo = (repo or REPO_ROOT).resolve()

    for required in ("review.json", "spec.json", "decisions.json"):
        if not (job / required).is_file():
            raise BuildError(f"eksik dosya: {required} (önce prepare ve approve çalıştırın)")

    review = read_json(job / "review.json")
    spec = read_json(job / "spec.json")

    plugin = resolve_plugin(repo, spec["slug"], spec["name"])
    if plugin is None:
        if not scaffold_missing:
            raise BuildError("eklenti dizini bulunamadı (--no-scaffold)")
        plugin = scaffold(repo, spec, review)

    # audit_job.py reads the job directory, so keep a copy of the Kotlin there.
    source_root = plugin / "src"
    if source_root.is_dir():
        for path in source_root.rglob("*.kt"):
            local = job / "src" / path.relative_to(source_root)
            local.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, local)

    ok, message = run_build(repo, plugin, job / "build.log")
    built_cs3 = find_cs3(plugin) if ok else None
    cs3_path = ""
    if built_cs3 is not None:
        target = job / built_cs3.name
        shutil.copy2(built_cs3, target)
        cs3_path = str(target)

    zip_path = zip_sources(plugin, job / f"{plugin.name}-source.zip")

    status = {
        "job": str(job),
        "plugin": plugin.name,
        "built": bool(ok and cs3_path),
        "cs3": cs3_path,
        "zip": str(zip_path),
        "log": str(job / "build.log"),
        "result": message,
        "playbackVerified": False,
        "playbackEvidence": "",
        "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "notes": [
            "built=true yalnızca paketleme kanıtıdır; oynatma ayrıca doğrulanmalıdır.",
            "playbackVerified, gerçek CloudStream oynatma denemesinden sonra elle true yapılır.",
        ],
    }
    (job / "status.json").write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return status
