# Kullanım Kılavuzu: Yeni Eklenti Nasıl Yapılır?

Bu kılavuz, bu depoya kendi elinle (ya da OpenCode / Claude yardımıyla) yeni bir CloudStream eklentisi
eklemeyi adım adım anlatır. Örnek olarak **Kanal D dizileri** eklentisini kullanıyoruz; hazır ve çalışan örnek
ise `TrtBelgesel/` klasörü.

---

## 0. Önce kısaca: sistem nasıl çalışıyor?

```
Sen kodu yazarsın  ──git push──▶  GitHub (main dalı)
                                     │
                                     ▼  GitHub Actions otomatik derler
                                 builds dalı:  plugins.json + EklentiAdi.cs3
                                     │
CloudStream (telefon) ◀── repo.json ─┘   "Eklentiler → Güncelle" deyince yeni sürümü indirir
```

- **Eklenti** = bir web sitesinden program listesini, bölümleri ve video adresini okuyup CloudStream'e veren küçük bir Kotlin programı.
- **`.cs3` dosyası** = derlenmiş eklenti.
- Senin işin sadece kodu yazmak ve `git push` yapmak; derleme ve yayınlama otomatik.

### Kaynak kuralı (önemli)
Bu depo **sadece resmi ve ücretsiz** kaynaklar içindir:
- ✅ Kanalın kendi sitesi, kanalın **resmi YouTube** kanalı, kanalın kendi sunucusundaki şifresiz canlı yayın.
- ❌ Korsan dizi/film siteleri, başka sitelere yüklenmiş kopyalar, ücretli üyelik/DRM/reklam atlatma.

**Kanal D için öneri:** Bölüm listesini `kanald.com.tr`'den al, videoyu **Kanal D'nin resmi YouTube kanalından** aç.
Videoyu sitenin oynatıcısından doğrudan çekmek, oradaki reklamları atlatmak anlamına gelir; bunu yapma.

---

## 1. Hazırlık (bir kez)

Laptopta her şey kurulu: Java 17, Android SDK (`~/Android/Sdk`), `git`, `gh` (GitHub'a giriş yapılmış).
Depo laptopta burada: `~/myprojects/cloudstream-eklentiler`

Başka bir bilgisayarda çalışacaksan:
```bash
gh repo clone altigenay/cloudstream-eklentiler
cd cloudstream-eklentiler
echo "sdk.dir=$HOME/Android/Sdk" > local.properties
```

Her çalışmaya başlamadan önce en güncel hali al:
```bash
cd ~/myprojects/cloudstream-eklentiler
git pull
```

---

## 2. Klasör yapısı

```
cloudstream-eklentiler/
├── repo.json                 ← CloudStream'e eklenen adres bu dosya (dokunma)
├── build.gradle.kts          ← ortak derleme ayarları (genelde dokunma)
├── settings.gradle.kts       ← klasörleri otomatik bulur (dokunma)
├── TrtBelgesel/              ← ÖRNEK eklenti
│   ├── build.gradle.kts      ← eklentinin adı, açıklaması, SÜRÜM NUMARASI
│   └── src/main/
│       ├── AndroidManifest.xml
│       └── kotlin/com/altigenay/trtbelgesel/
│           ├── TrtBelgeselPlugin.kt   ← eklentiyi kaydeder (3 satır)
│           └── TrtBelgesel.kt         ← ASIL KOD: liste, bölümler, video
└── KULLANIM.md               ← bu dosya
```

---

## 3. Yeni eklentiyi örnekten kopyala

```bash
cd ~/myprojects/cloudstream-eklentiler
cp -r TrtBelgesel KanalD
rm -rf KanalD/build
mv KanalD/src/main/kotlin/com/altigenay/trtbelgesel KanalD/src/main/kotlin/com/altigenay/kanald
cd KanalD/src/main/kotlin/com/altigenay/kanald
mv TrtBelgesel.kt KanalD.kt
mv TrtBelgeselPlugin.kt KanalDPlugin.kt
```

Sonra bu iki dosyada isimleri değiştir:
- `package com.altigenay.trtbelgesel` → `package com.altigenay.kanald`
- `class TrtBelgesel` → `class KanalD`, `class TrtBelgeselPlugin` → `class KanalDPlugin`
- `registerMainAPI(TrtBelgesel())` → `registerMainAPI(KanalD())`

`KanalD/build.gradle.kts` içinde:
```kotlin
version = 1
cloudstream {
    description = "Kanal D dizileri (resmi site + resmi YouTube)"
    authors = listOf("altigenay")
    status = 1
    tvTypes = listOf("TvSeries")
    language = "tr"
    iconUrl = "https://www.kanald.com.tr/favicon.ico"
}
```

---

## 4. Siteyi incele: hangi bilgi nerede?

Eklentinin yaptığı her şey 4 sorunun cevabı:

| Soru | Kodda karşılığı |
|---|---|
| Diziler hangi sayfada listeleniyor? | `getMainPage` |
| Bir dizinin bölümleri nerede? | `load` |
| Bir bölümün videosu nerede? | `loadLinks` |
| Dizi nasıl aranır? | `search` |

### Tarayıcıyla (en kolay)
1. Bilgisayarda Chrome/Brave ile `https://www.kanald.com.tr/diziler` sayfasını aç.
2. Bir dizi kartına **sağ tık → İncele (Inspect)**.
3. Açılan panelde kartın HTML'ini gör: dizi adı hangi etikette, resim nerede (`img src` / `data-src`), bağlantı (`a href`) nereye gidiyor?
4. Aynısını bir dizinin bölüm listesi sayfasında ve bir bölüm sayfasında yap.
5. Bölüm sayfasında videoyu bulmak için: **F12 → Network** sekmesi → sayfayı yenile → `youtube` ara.
   Ya da sayfa kaynağında (`Ctrl+U`) `application/ld+json`, `youtube.com/embed` ya da `contentUrl` ara.

### Terminalle (hızlı kontrol)
```bash
curl -sL -A "Mozilla/5.0" https://www.kanald.com.tr/diziler | grep -o 'href="/[^"]*"' | sort -u | head -30
```

### Seçici (selector) nedir?
Koddaki `doc.select("div.global--card")` gibi ifadeler sayfadaki öğeleri bulur:
- `div.global--card` → `class="global--card"` olan div'ler
- `a.link[href]` → `class="link"` olan ve `href`'i olan bağlantı
- `img[data-src]` → `data-src`'si olan resim
- `figcaption strong` → `figcaption` içindeki `strong`

Seçicileri, F12'de **Console** sekmesine şunu yazarak deneyebilirsin:
```js
document.querySelectorAll("div.global--card").length   // kaç kart bulundu?
```

---

## 5. Kodu uyarla (`KanalD.kt`)

`TrtBelgesel.kt`'deki yapıyı koru, sadece adresleri ve seçicileri değiştir:

1. **Başlık ayarları**
   ```kotlin
   override var mainUrl = "https://www.kanald.com.tr"
   override var name = "Kanal D"
   override val supportedTypes = setOf(TvType.TvSeries)
   ```
2. **Ana sayfa (`mainPage` + `getMainPage`)**: Diziler sayfasının adresi ve dizi kartı seçicileri.
   Canlı yayın kısmını (`canli...`) Kanal D için **sil**.
3. **`load`**: Dizi sayfasından bölümleri oku: bölüm adı, resmi, bağlantısı. Bölüm listesi birden çok sayfaya
   bölünmüşse (`?page=2` gibi) döngüyle hepsini topla.
4. **`loadLinks`**: Bölüm sayfasından **resmi YouTube adresini** bul ve şunu çağır:
   ```kotlin
   return loadExtractor(youtubeAdresi, data, subtitleCallback, callback)
   ```
   CloudStream YouTube videosunu kendisi oynatır.
5. **`search`**: Site araması varsa onun adresini kullan; yoksa TRT Belgesel'deki gibi bütün dizi listesinde ada göre filtrele.

---

## 6. Derle

```bash
cd ~/myprojects/cloudstream-eklentiler
./gradlew KanalD:make
```
- Başarılıysa: `KanalD/build/KanalD.cs3` oluşur.
- `w:` ile başlayan satırlar uyarıdır, sorun değil. **`e:` ile başlayan satırlar hatadır.**

| Hata | Çözüm |
|---|---|
| `incompatible version of Kotlin` | Kökteki `build.gradle.kts` → `kotlin-gradle-plugin` sürümünü yükselt |
| `Type annotation ... inaccessible` | Değişkenin türünü açıkça yaz: `val img: Element = selectFirst("img") ?: return null` |
| `Unresolved reference` | Yazım hatası ya da eksik `import com.lagradost.cloudstream3.*` / `utils.*` |

---

## 7. Yayınla

```bash
git add -A
git commit -m "Kanal D eklentisi eklendi"
git push
```
GitHub'da **Actions** sekmesinden derlemeyi izle (ya da terminalden):
```bash
gh run list -L 3
```
Yeşil ✓ olunca eklenti `builds` dalına konmuştur. Kırmızı ✗ ise:
```bash
gh run view --log-failed
```

**Her değişiklikten sonra** eklentinin `build.gradle.kts` dosyasındaki `version` sayısını 1 artır
(1 → 2 → 3). Yoksa telefondaki CloudStream güncellemeyi görmez.

---

## 8. Telefonda dene

1. CloudStream → **Ayarlar → Eklentiler**.
2. Depo eklenmemişse: **Depo ekle** →
   `https://raw.githubusercontent.com/altigenay/cloudstream-eklentiler/main/repo.json`
3. Depoya gir → **Kanal D** → indir. Güncelleme için depoda **güncelle** simgesine bas.
4. Ana sayfada sağ üstten kaynak olarak **Kanal D**'yi seç; liste, bölümler ve oynatmayı dene.
5. Hata görürsen: CloudStream → Ayarlar → **Günlükleri (log) paylaş**. Bu kaydı OpenCode'a ya da Claude'a ver.

---

## 9. OpenCode ya da Claude ile yaptırmak (en kolay yol)

Bu depoya özel **`cloudstream-eklenti`** becerisi OpenCode'da ve Claude Code'da kurulu.
Becerinin içinde bu deponun yapısı, kuralları, derleme ve yayınlama adımları var.
Terminalde bu klasörde OpenCode'u (ya da OpenChamber'ı) aç ve şöyle yaz:

**Yeni eklenti:**
> cloudstream-eklenti becerisini kullan. Kanal D dizileri için eklenti yap: dizi listesi ve bölümler
> kanald.com.tr'den gelsin, videolar Kanal D'nin resmi YouTube kanalından açılsın. Önce siteyi incele,
> seçicileri canlı sitede doğrula, sonra derle ve push et.

**Düzeltme:**
> cloudstream-eklenti becerisiyle KanalD eklentisinde bölüm listesi boş geliyor, düzelt. Sürümü artırıp push et.

**Günlükle hata ayıklama:**
> cloudstream-eklenti becerisiyle şu CloudStream günlüğüne bak ve KanalD eklentisini düzelt: (günlüğü yapıştır)

İpuçları:
- Ne istediğini net söyle: hangi site, hangi bölüm, ne çalışmıyor.
- Ajanın "derlendi" demesi oynadığı anlamına gelmez; telefonda dene ve sonucu ona söyle.
- Ajan bir şeyi korsan kaynaktan yapmak isterse ya da reklam/üyelik atlatmayı önerirse, yapma demen gerekmez;
  beceri zaten izin vermez.

---

## 10. Hızlı başvuru

| Ne yapacağım? | Komut |
|---|---|
| Güncel hali al | `git pull` |
| Derle | `./gradlew EklentiAdi:make` |
| Hepsini derle | `./gradlew make` |
| Yayınla | `git add -A && git commit -m "mesaj" && git push` |
| Derleme durumu | `gh run list -L 3` |
| Derleme hatası | `gh run view --log-failed` |
| Sürüm artır | `EklentiAdi/build.gradle.kts` → `version = N+1` |
