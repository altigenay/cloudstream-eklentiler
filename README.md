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

## Geliştirme
- Yeni eklenti: kök dizinde `EklentiAdi/` klasörü (`build.gradle.kts` + `src/main/kotlin/...`); `settings.gradle.kts` otomatik ekler.
- Yerel derleme: `./gradlew EklentiAdi:make` → `EklentiAdi/build/EklentiAdi.cs3` (Android SDK yolu `local.properties` içinde).
- `main`'e gönderilen her değişiklikte GitHub Actions eklentileri derleyip `builds` dalına koyar.
- Değişiklikte eklentinin `build.gradle.kts` içindeki `version` artırılır.
