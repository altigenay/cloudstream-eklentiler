# Yerel notlar (studio + depo kuralları)

Bu dosya, CloudStream resmi dokümanları (`docs/cloudstream/`) ile
`cloudstream-builder` skill referanslarının bu depo için birleştirilmiş özetidir.
Çelişki olursa sıra: bu dosya → `SKILL.md` → `docs/cloudstream/`.

## İş sözleşmesi (studio)

Bir eklenti işi dört dosyayla tanımlanır (`python -m turkstream_studio.workflow`):

| Dosya | Üreten | İçerik |
|---|---|---|
| `review.json` | `prepare` | bulunan kart bölümleri, seçiciler, örnek kartlar, sinyaller |
| `spec.json` | `prepare` / `approve` | eklenti adı, slug, baseUrl, tür, mainPage listesi |
| `decisions.json` | `approve` | onaylanan roller (`media`/`text`/`ignore`) ve veri değerleri |
| `status.json` | `build` | `built`, `cs3`, `zip`, `playbackVerified`, `playbackEvidence` |

`built=true` yalnızca **paketleme** kanıtıdır. `playbackVerified` gerçek
CloudStream oynatma denemesinden sonra elle `true` yapılır ve `playbackEvidence`
alanına kanıt yazılır.

## Depo düzeni

- Her eklenti kök dizinde kendi klasöründe: `<Eklenti>/build.gradle.kts` + `src/main/kotlin/...`.
- `settings.gradle.kts` `build.gradle.kts` içeren her klasörü otomatik dahil eder.
- Derleme: `./gradlew <Eklenti>:make` → `<Eklenti>/build/<Eklenti>.cs3`.
- `main` her push'ta GitHub Actions paketleri derler ve `builds` dalına yazar;
  `repo.json` (main) `builds/plugins.json`'a işaret eder.
- Sürüm artışı `build.gradle.kts` içindeki `version` alanındadır; artmazsa
  CloudStream güncellemeyi görmez.

## Kaynak kuralları (zorunlu)

- **Tek sunucu, tek kaynak:** Aynı sunucunun 1080p/720p/480p varyantları ayrı
  `ExtractorLink` olarak yayınlanmaz. Gerçek bir HLS master varsa tek
  `ExtractorLinkType.M3U8` verilir; kaliteler oynatıcının **Parçalar** menüsünde
  görünür. Master yoksa sunucu başına tek (en iyi) doğrulanmış link verilir.
- MP4'ü M3U8 diye etiketlemek yasak; kaynağın gerçek türü korunur.
- Fragman linkleri `loadLinks` içine konmaz, yalnızca `addTrailer` alanına gider.
- Yalnızca resmi/ücretsiz kaynaklar; video indirme veya yeniden yayınlama yok.

## Kazıma pratiği

- Önce oynatma linkini çöz, sonra katalog yaz: link çözülemiyorsa eklenti işe yaramaz.
- iframe → ayrı sekmede aç → `.m3u8`/`.mp4` isteğini bul → isteği geriye doğru izle.
- Gerekli başlıklar: `User-Agent`, `Referer`, `Origin`, `X-Requested-With`, bazen `Cookie`.
- Base64 (`==` ile biter), AES (`enc`, `iv`, `CryptoJS`) ve JS ile üretilen linkler
  yaygın gizleme yöntemleridir; JS üretimi varsa tarayıcı hata ayıklayıcısı gerekir.
- Cloudflare/captcha varsa: sahte token, arka plan WebView veya captcha'sız payload.
- jQuery/JS ile çizilen kartlar HTML'de görünmez; `prepare` bunu "az bağlantı"
  uyarısıyla bildirir, o zaman tarayıcı ağ kaydı şart.

## Yayın öncesi geçitler

1. `python scripts/audit_job.py <JOB>` → hata yok (uyarılar gerekçelendirilir).
2. `./gradlew <Eklenti>:make` → `.cs3` üretildi.
3. `node scripts/verify_remote_repo.mjs <repo.json>` → yayın zinciri eşleşti.
4. Gerçek oynatma denemesi (CloudStream, cihaz) → `status.json` güncellenir.

## Bilgi indeksi

`python -m turkstream_studio.workflow docs "<soru>"` hem bu depodaki skill
referanslarını hem `docs/cloudstream/` altındaki resmi dokümanları arar ve
`dosya:satır` döndürür. Cevap uydurmak yerine kaynağı açıp okumak için kullanılır.
