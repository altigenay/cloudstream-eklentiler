# CloudStream developer documentation (snapshot)

Bu klasör, CloudStream'un resmi geliştirici dokümanlarının yerel bir kopyasıdır.
Studio'nun bilgi indeksi (`turkstream_studio/knowledge.py`) bu dosyaları
`SKILL.md` + `references/` + `extractors/INDEX.md` ile birlikte indeksler.

- Kaynak: <https://recloudstream.github.io/csdocs/> — depo: <https://github.com/recloudstream/csdocs>
- Alınma: 2026-10-24, `main` dalı, 34 markdown dosyası
- Kapsam: `devs/` (eklenti geliştirme, kazıma), `Settings/`, `Integrations/`,
  `Other devices/`, `More Stuff/`, `Repositories.md`, `recapps.md`, `index.md`
- Biçim: dosyalar kaynaktan **değiştirilmeden** kopyalanmıştır (frontmatter dahil);
  yalnızca dizin yapısı korunmuştur.

Bu içerik CloudStream topluluğuna aittir ve burada yalnızca yerel referans /
arama amacıyla tutulur. Güncellemek için:

```bash
python -m turkstream_studio.workflow docs "hls master"
# veya kaynaktan yeniden çekmek için:
git clone --depth 1 https://github.com/recloudstream/csdocs /tmp/csdocs
```

Yerel ek notlar (bu depoya özgü kurallar) `docs/local-notes.md` içindedir.
