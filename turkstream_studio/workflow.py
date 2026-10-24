"""TurkStream Studio (local): deterministic CloudStream provider workflow.

Same job contract the cloudstream-builder skill already documents
(`review.json`, `spec.json`, `decisions.json`, `status.json`), implemented with
the Python standard library so it runs on a clean Linux machine, plus a merged
knowledge index over the CloudStream developer documentation.

Commands
    prepare URL OUTPUT [--kind movie|live] [--language tr]
    approve JOB [--set SELECTOR=ROLE ...]
    build JOB [--repo DIR] [--no-scaffold]
    docs QUERY [--limit N] [--source skill|csdocs]
    doctor
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import build as build_module
from . import discover, knowledge

ROLES = {"media", "text", "ignore"}


def _fail(message: str) -> int:
    print(f"HATA {message}", file=sys.stderr)
    return 1


def cmd_prepare(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    result = discover.fetch(args.url)
    if not result.ok:
        return _fail(f"sayfa alınamadı ({result.status}) {args.url}: {result.content_type}")

    review = discover.discover(result.text, result.final_url)
    review["url"] = result.final_url
    review["requestedUrl"] = args.url
    review["status"] = result.status
    review["elapsedMs"] = result.elapsed_ms
    kind = args.kind or discover.detect_kind(review)
    review["kind"] = kind

    job = output / discover.slugify(review.get("siteName") or review.get("pageTitle") or "job")
    if job.exists() and not args.force:
        return _fail(f"iş klasörü zaten var: {job} (--force ile üzerine yaz)")
    job.mkdir(parents=True, exist_ok=True)
    discover.write_review(job, review)

    spec = discover.build_spec(review, kind, args.language)
    (job / "spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"JOB {job}")
    print(f"KIND {kind}  SECTIONS {len(review['sections'])}  ANCHORS {review['signals']['anchors']}")
    for section in review["sections"]:
        sample = section["samples"][0]["title"] if section["samples"] else "-"
        print(f"  [{section['id']}] {section['title'][:40]:42} kart={section['count']:<3} örnek={sample[:40]}")
    for warning in review["warnings"]:
        print(f"UYARI {warning}")
    print("SONRAKI: bölümlere rol ver (media/text/ignore), sonra: approve", job.name)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    job = Path(args.job).expanduser().resolve()
    review_path = job / "review.json"
    if not review_path.is_file():
        return _fail(f"review.json yok: {job}")

    review = json.loads(review_path.read_text(encoding="utf-8"))
    overrides: dict[str, str] = {}
    for value in args.set or []:
        if "=" not in value:
            return _fail(f"--set biçimi SELİM=ROL olmalı: {value}")
        selector, role = value.rsplit("=", 1)
        if role not in ROLES:
            return _fail(f"geçersiz rol: {role} (media|text|ignore)")
        overrides[selector] = role

    sections = review.get("sections") or []
    # Re-running approve keeps previously approved roles (idempotent).
    decisions_path = job / "decisions.json"
    if decisions_path.is_file():
        try:
            previous = json.loads(decisions_path.read_text(encoding="utf-8"))
            known = {item["id"]: item.get("role") for item in previous.get("sections", [])}
            for section in sections:
                if section.get("role") not in ROLES and known.get(section["id"]) in ROLES:
                    section["role"] = known[section["id"]]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    for section in sections:
        for key in (section["id"], section["selector"]):
            if key in overrides:
                section["role"] = overrides[key]

    included = [section for section in sections if section.get("include")]
    missing = [section["id"] for section in included if section.get("role") not in ROLES]
    if missing:
        print("Rol verilmemiş bölümler: " + ", ".join(missing))
        for section in included:
            if section.get("role") not in ROLES:
                print(f"  [{section['id']}] {section['selector']}  -> {section['title']}")
        return _fail("her dahil bölüm için rol gerekli: media/text/ignore")

    media = [section for section in included if section.get("role") == "media"]
    if not media:
        return _fail("en az bir media bölümü gerekli")

    approved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    decisions = {
        "approvedAt": approved_at,
        "url": review.get("url"),
        "kind": review.get("kind"),
        "sections": [
            {
                "id": section["id"],
                "title": section["title"],
                "selector": section["selector"],
                "role": section["role"],
                "data": section.get("data") or section["id"],
            }
            for section in included
        ],
        "counts": {
            "media": len(media),
            "text": sum(1 for section in included if section.get("role") == "text"),
            "ignore": sum(1 for section in included if section.get("role") == "ignore"),
        },
    }
    (job / "decisions.json").write_text(json.dumps(decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # audit_job.py reads roles from review.json; keep both files in sync.
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    spec = json.loads((job / "spec.json").read_text(encoding="utf-8"))
    spec["mainPage"] = [
        {"name": section["title"], "data": section.get("data") or section["id"], "selector": section["selector"]}
        for section in media
    ]
    (job / "spec.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"ONAY {len(media)} media, {decisions['counts']['text']} text, {decisions['counts']['ignore']} ignore -> {job.name}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    job = Path(args.job).expanduser().resolve()
    try:
        status = build_module.build(job, Path(args.repo).expanduser() if args.repo else None,
                                    scaffold_missing=not args.no_scaffold)
    except build_module.BuildError as error:
        return _fail(str(error))
    print(json.dumps(status, indent=2, ensure_ascii=False))
    print(f"SONUÇ {'derlendi' if status['built'] else 'derlenemedi'} ({status['result']})")
    print("NOT oynatma doğrulanmadı; status.playbackVerified=false")
    return 0 if status["built"] else 1


def cmd_docs(args: argparse.Namespace) -> int:
    index = knowledge.Index()
    hits = index.search(args.query, limit=args.limit, source=args.source)
    if not hits:
        print("eşleşme yok")
        return 1
    for score, chunk in hits:
        print(f"{score:6.2f}  {chunk.source:6}  {chunk.path}:{chunk.line}  [{chunk.heading}]")
        preview = " ".join(chunk.text.split())[:220]
        print(f"        {preview}")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    repo = build_module.REPO_ROOT
    index = knowledge.Index()
    stats = index.stats()
    plugins = sorted(path.name for path in build_module.plugin_dirs(repo).values())
    print(f"depo          {repo}")
    print(f"python        {sys.version.split()[0]}")
    print(f"gradlew       {'var' if (repo / 'gradlew').is_file() else 'YOK'}")
    print(f"Android SDK   {(repo / 'local.properties').read_text().strip() if (repo / 'local.properties').is_file() else 'local.properties yok'}")
    print(f"eklentiler    {', '.join(plugins) or '-'}")
    print(f"bilgi indeksi {stats['chunks']} bölüm / {stats['files']} dosya {stats['bySource']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m turkstream_studio.workflow", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="siteyi keşfet, iş klasörü oluştur")
    prepare.add_argument("url")
    prepare.add_argument("output")
    prepare.add_argument("--kind", choices=["movie", "live"])
    prepare.add_argument("--language", default="tr")
    prepare.add_argument("--force", action="store_true")
    prepare.set_defaults(func=cmd_prepare)

    approve = sub.add_parser("approve", help="bölüm rollerini onayla")
    approve.add_argument("job")
    approve.add_argument("--set", action="append", metavar="SELECTOR=ROLE")
    approve.set_defaults(func=cmd_approve)

    build_cmd = sub.add_parser("build", help="paketle (.cs3 + kaynak zip)")
    build_cmd.add_argument("job")
    build_cmd.add_argument("--repo")
    build_cmd.add_argument("--no-scaffold", action="store_true")
    build_cmd.set_defaults(func=cmd_build)

    docs = sub.add_parser("docs", help="birleşik bilgi indeksinde ara")
    docs.add_argument("query")
    docs.add_argument("--limit", type=int, default=8)
    docs.add_argument("--source", choices=["skill", "csdocs"])
    docs.set_defaults(func=cmd_docs)

    doctor = sub.add_parser("doctor", help="kurulumu denetle")
    doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
