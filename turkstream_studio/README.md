# TurkStream Studio (yerel sürüm)

CloudStream eklentisi üretimini deterministik bir iş akışına bağlar:
**keşfet → onayla → paketle → denetle**. Yalnızca Python standart kütüphanesi ve
depodaki Gradle wrapper'ı kullanır; ek kurulum gerektirmez.

## Komutlar

```bash
cd ~/.agents/skills/cloudstream-builder

# 1) Siteyi keşfet: review.json + spec.json
python -m turkstream_studio.workflow prepare https://ornek.site studio-jobs

# 2) Bölümlere rol ver (media | text | ignore), sonra onayla
python -m turkstream_studio.workflow approve studio-jobs/ornek-site \
    --set s1=text --set s2=media

# 3) Paketle: .cs3 + kaynak zip + status.json
python -m turkstream_studio.workflow build studio-jobs/ornek-site

# 4) Yapısal denetim
python scripts/audit_job.py studio-jobs/ornek-site

# Bilgi indeksi (skill + resmi CloudStream dokümanları)
python -m turkstream_studio.workflow docs "hls master tek kaynak"
python -m turkstream_studio.workflow doctor
```

`prepare` çıktısı: her tekrar eden kart bloğu için seçici, kart sayısı, örnek
kartlar ve bir rol önerisi (`suggestedRole`). Öneri bağlayıcı değildir; `role`
alanı `approve` çalışana kadar boş kalır, böylece hiçbir bölüm sessizce
"media" sayılmaz.

`build`, iş klasöründe Kotlin yoksa onaylanmış `spec.json`'dan iskelet üretir
(`TODO(studio)` işaretleriyle) ve derlemeyi dener. İskelet derlenmiyorsa
`status.json` içinde `built=false` yazar; sahte başarı üretmez.

## Dosyalar

| Modül | Görev |
|---|---|
| `htmltree.py` | stdlib HTML ağacı + CSS-lite seçici motoru (`div.card > a`, `[href^=]`) |
| `discover.py` | sayfa çekme, kart bloğu bulma, tekrar eden menüleri eleme, `review.json` |
| `build.py` | iş sözleşmesi denetimi, iskelet, `gradlew <Eklenti>:make`, `status.json` |
| `knowledge.py` | `docs/cloudstream/` + skill referansları üzerinde BM25 arama |
| `workflow.py` | CLI |

## Sınırlar

- JavaScript ile çizilen sayfalarda kartlar HTML'de olmaz; `prepare` uyarır,
  tarayıcı ağ kaydı (`references/browser-devtools-to-provider.md`) gerekir.
- `prepare`/`build` ağ üzerinden yalnızca hedef siteyi okur; hiçbir veriyi dışarı
  göndermez, kimlik bilgisi saklamaz.
- Oynatma doğrulaması yapmaz; `status.json` bunu açıkça `false` bırakır.
