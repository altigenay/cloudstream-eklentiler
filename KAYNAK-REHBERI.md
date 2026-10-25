# Kaynak Rehberi: Bu depoda neyi kullanabilirim, neyi kullanmamalıyım?

Bu depoya sonradan bir "CloudStream Builder" becerisi ve yanında ~90 hazır **çözücü (extractor)** eklendi.
Bu çözücülerin bir kısmı **korsan film/dizi sitelerinin** video oynatıcıları için yazılmış. Bu rehber, hangi
dosyanın ne olduğunu ve neyi güvenle kullanabileceğini anlatır. (Kendi eklentini adım adım yapmak için: [KULLANIM.md](KULLANIM.md))

## Önce temel kural: Yasal mı, nasıl anlarım?

Bir kaynak **yasal** sayılır, eğer:
1. İçeriği yayınlayan **hak sahibinin kendisi** (kanal, yapımcı, kurum) ise: `kanald.com.tr`, `trtbelgesel.com.tr`, kanalın **resmi** YouTube hesabı.
2. İçerik **ücretsiz ve üyeliksiz** sunuluyorsa. Ücretli / üyelikli içerik için eklenti yapılmaz.
3. Eklenti **koruma atlatmıyorsa**: DRM, reklam, üyelik, bölge kısıtı yok.
4. İçerik **kamu malı** (telif süresi dolmuş) ya da sahibi açık lisansla paylaşmışsa (ör. Internet Archive'daki kamu malı filmler).

Bir kaynak **yasal değildir**, eğer:
- Site, başkasına ait filmleri/dizileri izinsiz koyuyorsa: adında "film izle", "dizi izle", "hdfilm", "full izle" geçen
  siteler, Netflix/Disney/BluTV dizilerini ücretsiz veren siteler, sürekli alan adı değiştiren siteler
  (`.fat`, `.top`, `.pro`, `.to` gibi).
- Video, kimin yüklediği belli olmayan **dosya barındırma servislerinden** geliyorsa (Voe, StreamHG, LuluStream, Filedon…).

**Hızlı test:** "Bu içeriği izlemek için normalde para ya da üyelik gerekir mi? Siteyi işleten, içeriğin sahibi mi?"
Cevap "evet, para gerekir" ya da "hayır, sahibi değil" ise o kaynak için eklenti yapma.

---

## 🟢 Güvenle kullanabileceklerin

### Eklentiler
| Klasör | Kaynak | Durum |
|---|---|---|
| `TrtBelgesel/` | trtbelgesel.com.tr + TRT Belgesel resmi YouTube + resmi şifresiz canlı yayın | ✅ Yasal, örnek olarak kullan |
| `ArsivSinema/` | archive.org `feature_films` koleksiyonu | ⚠️ Çoğu kamu malı, ama bu koleksiyonda telifli filmlerin izinsiz yüklemeleri de bulunabiliyor. Daha güvenli olması için yalnızca kamu malı/açık lisanslı öğelere filtrelenmeli (`licenseurl` ya da `publicdomain` koleksiyonu). |
| `Tabii/` | tabii.com (TRT'nin ücretsiz platformu) | ⚠️ İçerik ücretsiz, ama çoğu bölüm **Widevine DRM** ile korunuyor ve eklenti DRM lisansını tabii'nin sunucusundan uygulama dışında alıyor. Bu, kullanım şartlarına aykırı olabilir. Güvenli kullanım: yalnızca DRM'siz bölümler ya da resmi canlı yayın. |

### Araçlar (yasal/korsan fark etmez, nötr)
| Dosya | Ne işe yarar | Nasıl kullanılır |
|---|---|---|
| `scripts/verify_repo_integrity.py` | `plugins.json` içindeki `version`, `fileSize`, `fileHash` ile `.cs3` dosyasını karşılaştırır | `python3 scripts/verify_repo_integrity.py .` (düzeltmek için `--fix`) |
| `scripts/verify_remote_repo.mjs` | GitHub'daki `repo.json` → `plugins.json` → `.cs3` zincirini indirip kontrol eder | `node scripts/verify_remote_repo.mjs https://raw.githubusercontent.com/altigenay/cloudstream-eklentiler/main/repo.json` |
| `scripts/audit_provider_contracts.py`, `audit_job.py` | Eklenti kodunda eksik fonksiyon / yaygın hataları arar | `python3 scripts/audit_provider_contracts.py TrtBelgesel` |
| `scripts/scan_provider_patterns.py` | Bir eklenti klasörünün kısa envanterini çıkarır | `python3 scripts/scan_provider_patterns.py .` |
| `docs/cloudstream/` | CloudStream'in resmi belgelerinin kopyası (eklenti geliştirme, ayarlar, sorun giderme) | Okumak için |
| `references/hls-master.md`, `playback.md`, `browser-devtools-to-provider.md`, `site-architectures.md` | Teknik notlar: HLS kalite seçimi, oynatma, tarayıcıdan veri bulma | Teknik bilgi olarak okunabilir. Örneklerdeki site adlarına bakma, yönteme bak. |
| `extractors/oce/core/` | Çözücü motoru (yapılandırma dosyasından çözücü üretir) | Kendi başına bir siteye bağlı değil |
| `extractors/oce/kotlin/AdaptiveQualityPicker.kt`, `M3u8MasterVerifier.kt`, `AdaptiveHeaderProbe.kt`, `CompiledRegexPatterns.kt` | Genel yardımcılar (kalite seçimi, m3u8 kontrolü) | Resmi bir HLS kaynağında kullanılabilir |

### Genel video platformları: duruma göre
Bunlar herkesin yükleme yapabildiği platformlar. **Video, içeriğin sahibinin resmi hesabından** yüklenmişse kullanılabilir;
herhangi birinin yüklediği film/dizi kopyası ise kullanılamaz.

| Çözücü | Platform |
|---|---|
| `DailymotionExtractor`, `Dailymotion.json` | Dailymotion |
| `RumbleExtractor`, `Rumble.json`, `Odysee.json`, `DTube.json` | Rumble, Odysee, DTube |
| `BloggerVideoExtractor` | Blogger/Google video |
| `turk/OdnoklassnikiExtractor`, `OkRuExtractor`, `oce/OdnoklassnikiExtractor` | OK.ru |
| `turk/VkExtractor` | VK |
| `turk/DzenExtractor` | Yandex Dzen |
| `turk/SibNetExtractor` | Sibnet |
| `turk/DiskYandexComTrExtractor`, `turk/DriveExtractor`, `turk/PixelDrainExtractor`, `KrakenfilesExtractor` | Yandex Disk, Google Drive, Pixeldrain, Krakenfiles (dosya paylaşım) |

> Not: Türk kanallarının resmi videoları neredeyse her zaman **YouTube**'dadır ve CloudStream YouTube'u kendisi oynatır.
> Yukarıdaki platformlara pek ihtiyacın olmaz.

---

## 🔴 Kullanma: korsan sitelerin oynatıcıları

Bu çözücüler, depodaki `extractors/INDEX.md`'nin de yazdığı gibi, izinsiz film/dizi sitelerinin
(ör. FilmMakinesi, HDFilmcehennemi, HDFilmizle, NetFilmizle, SetFilmizle, DiziMom, Sinemakolik)
video oynatıcılarını ve izinsiz yükleme yapılan dosya barındırma servislerini çözmek için yazılmış.
**Bunlarla eklenti yapma.**

### `extractors/turk/`
`CloseLoad`, `HCCloseLoad`, `HCRapidrame`, `RapidVid`, `VidRame`, `FirePlayer`, `Vidmixi`, `VidMoxy`, `SetPlay`,
`FastPlay`, `HDMomPlayer`, `HDPlayerSystem`, `HDStreamAble`, `ContentX`, `TurkeyPlayer`, `Hotlinger`, `PeaceMakerst`,
`TRsTX`, `TauVideo`, `W2M`, `TurboImgz`, `Sobreatsesuyp`, `CineStreamExtractors`, `CizgiDuo`, `CizgiPass`,
`PlayerKorea`, `VideoSeyred`, `Extractors.kt` (bunların toplu kaydı)

### `extractors/oce/kotlin/` ve `configs/`
`Abyss*`, `Anichin*`, `Anonmp4`, `AWSStream`, `ByseSX*`, `Cloudhownetwork`, `Hownetwork`, `CyberJunkiePage`,
`Dhcplay`, `EmbedPyrox`, `EmTurbovid`, `Filedon`, `Gdplayer`, `Lk21*` (Endonezya korsan film sitesi), `LuluStream`,
`MegaPlay`, `Minochinos`, `Morencius`, `Movearnpre`, `PlayCdn`, `PlayMogo`, `PlayPutarIn`, `PlayStreamplay`,
`PlayStreamVideo`, `SamehadakuPage` (korsan anime sitesi), `ShortIcu`, `StreamHG`, `StreamRuby`, `Svanila`, `Svilla`,
`VeevTo`, `VideoNode*`, `VideoplayerVip`, `Vidguard*`, `Voe`, `Wishfast`, `Xtwap`, `JsPackerDecoder`
(korsan oynatıcıların gizlenmiş kodunu çözmek için)

### Beceri dosyaları
| Dosya | Neden dikkat |
|---|---|
| `SKILL.md` (kökteki), `agents/openai.yaml` | CloudStream Builder becerisi: "siteyi cs3 yap" mantığıyla her film/dizi sitesinden eklenti üretmeye yönlendirir ve bu çözücü kütüphanesini kullanır. Ajana bu beceriyle iş verirsen korsan siteye eklenti yapmaya çalışabilir. Bunun yerine **`cloudstream-eklenti`** becerisini kullan. |
| `scripts/auto_heal_all_repos.py`, `scripts/skill_sync.sh` | Beceriyi otomatik günceller ve otomatik `git push` yapar. Kaynağından güncellendikçe kaldırdığın kısımlar geri gelebilir. Otomatik çalıştırma (cron, zamanlayıcı) kurma. |
| `references/movie-series.md`, `fast-streaming-aggregator.md`, `proven-repository-patterns.md` | Örnekleri korsan film/dizi sitelerinden. Yöntem bilgisi olarak okunabilir, ama örnek siteleri hedefleme. |
| `turkstream_studio/` | Herhangi bir siteden otomatik eklenti iskeleti çıkaran araç. Araç nötr, ama sadece yasal bir siteye uygula. |

---

## Ajanlara (OpenCode / Claude) iş verirken

- Her zaman **`cloudstream-eklenti`** becerisini adıyla iste: "cloudstream-eklenti becerisini kullanarak…"
- Kaynağı açıkça söyle: "resmi site + resmi YouTube".
- Ajan kırmızı listedeki bir çözücüyü ya da adında "film izle / dizi izle" geçen bir siteyi kullanmak isterse durdur.

## İstersen temizlik

Kırmızı listedeki dosyaları depodan tamamen kaldırmak istersen, OpenCode'a ya da Claude'a şunu söyleyebilirsin:
> KAYNAK-REHBERI.md'deki 🔴 listesindeki çözücüleri ve CloudStream Builder becerisini depodan kaldır,
> derlemenin bozulmadığını kontrol et ve push et.

Bu dosyalar derlenen eklentilere bağlı değil (yalnızca `TrtBelgesel`, `Tabii`, `ArsivSinema` derleniyor);
kaldırmak çalışan eklentileri etkilemez.
