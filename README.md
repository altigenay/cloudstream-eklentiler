# Altigenay CloudStream Eklentileri

Yalnızca resmi ve ücretsiz kaynaklar için CloudStream eklentileri. Eklentiler videoyu indirmez ya da yeniden yayınlamaz;
kaynağın kendi resmi oynatıcısının kullandığı adresi açar.

## Kurulum
CloudStream → Ayarlar → Eklentiler → Depo ekle:

```
https://raw.githubusercontent.com/altigenay/cloudstream-eklentiler/main/repo.json
```

## Eklentiler
| Eklenti | Kaynak | İçerik |
|---|---|---|
| TRT Belgesel | trtbelgesel.com.tr | 9 kategorideki programlar ve bölümler (TRT Belgesel'in resmi YouTube videoları), resmi canlı yayın |

## CloudStream Builder skill (bu makine)

Bu depo aynı zamanda `cloudstream-builder` becerisinin kurulu olduğu yerdir:
`~/.agents/skills/cloudstream-builder` bu deponun bir checkout'udur.

- `scripts/`, `references/`, `extractors/`, `tests/`, `agents/`, `assets/` — becerinin araçları ve kitaplıkları.
- `scripts/skill_sync.sh pull|push|audit|status` — depoyu eşitler, değişiklikleri bu depoya gönderir, yayın zincirini denetler.
- `systemd` zamanlayıcısı `cloudstream-skill-sync.timer` her 15 dakikada `pull` çalıştırır; beceri kendini bu depodan otomatik günceller.
- Yardımcı betiklerin yolları `scripts/csconfig.py` içindedir (`CLOUDSTREAM_REPOS`, `CLOUDSTREAM_OUTPUT`, `CLOUDSTREAM_BRANCH` ile değiştirilebilir).

## Geliştirme
Adım adım anlatım: [KULLANIM.md](KULLANIM.md) · Hangi kaynak/dosya güvenli: [KAYNAK-REHBERI.md](KAYNAK-REHBERI.md)

- Yeni eklenti: kök dizinde `EklentiAdi/` klasörü (`build.gradle.kts` + `src/main/kotlin/...`); `settings.gradle.kts` otomatik ekler.
- Yerel derleme: `./gradlew EklentiAdi:make` → `EklentiAdi/build/EklentiAdi.cs3` (Android SDK yolu `local.properties` içinde).
- `main`'e gönderilen her değişiklikte GitHub Actions eklentileri derleyip `builds` dalına koyar.
- Değişiklikte eklentinin `build.gradle.kts` içindeki `version` artırılır.
