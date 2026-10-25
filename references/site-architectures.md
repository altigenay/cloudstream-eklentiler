# Site Mimarileri — Keşif Karar Ağacı

Bir siteyi sağlayıcıya çevirmeden önce **mimarisini** teşhis et; yanlış yol seçmek en çok zaman kaybettiren hatadır. Bu belge, gerçek keşiflerden çıkmış tarifleri ve `prepare` çıktısındaki sinyalleri nasıl okuyacağınızı anlatır.

**Kaynak kuralı (değişmez):** yalnız **resmi ve ücretsiz** kaynaklar (yayıncıların kendi siteleri, resmi kanallar, kamuya açık arşivler). Korsan/yetkisiz siteler bu skill ile kapsam dışıdır; "test amaçlı" olsa bile.

## 0) Mimari teşhisi

`python -m turkstream_studio.workflow prepare URL JOB` çıktısındaki `signals` alanına bak:

| Sinyal | Mimari | Yol |
|---|---|---|
| `anchors` yüksek, `sections` dolu | SSR HTML kart siteleri | 1 |
| `embeddedJson` var (`__NEXT_DATA__`, `__NUXT__`, `__INITIAL_STATE__`) | SPA + sunucuda gömülü JSON | 2 |
| Bağlantı yok, `nextAssets` var, JSON yok | Saf istemci SPA | 3 |
| `apiHints` dolu (fetch/axios çağrıları) | JSON API öncelikli | 4 |
| Liste SSR, arama kutusu AJAX (`wire:snapshot`, `livewire`) | SSR + AJAX/Livewire | 5 |
| Akış `widevine`/`fps`/`playready` sözcükleri | DRM'li yayın | 6 |

Aynı sitede katmanlar karışabilir (liste SSR, detay istemci; katalog SSR, arama AJAX). Her katmanı ayrı teşhis et.

## 1) SSR HTML kart siteleri (temel yol)

Zaten `prepare`/`approve` akışının ana yoludur: tekrar eden kart blokları → seçiciler → Kotlin.
Örnek: TRT Belgesel (`figure > img + figcaption a`), haber/video sitelerinin çoğu.
Kural: `review.json`'daki öneriyi ezme; `approve` yazmadan hiçbir bölüm `media` sayılmaz.

## 2) SPA + sunucuda gömülü JSON (`__NEXT_DATA__` vb.)

Sayfa JS ile çizilir AMA veri HTML içinde gömülüdür — ağ kaydı bile gerekmez.

1. HTML'de `<script id="__NEXT_DATA__" type="application/json">` (Next.js), `__NUXT__` (Nuxt), `window.__INITIAL_STATE__`/`window.__APOLLO_STATE__` ara.
2. Gömülü JSON'dan **içerik kimliklerini** çıkar: `id`, `slug`, `title`, `images[].name`, `contentType`.
3. URL kalıbını kur: genelde `/{dil}/detail/{id}/{slug}` veya `/{id}-{slug}`. Gerçek bir detay sayfasını `curl` ile doğrula (SSR'de `pageProps.data` dolu gelmeli).
4. Sağlayıcıda her şeyi bu JSON'lardan oku: katalog grupları (ana sayfa `carousel/promoter` gibi diziler), `seasons[].episodes[]`, `localization` (ses dilleri + altyazılar).
5. Next.js veri yolu da denenebilir: `/_next/data/{buildId}/{rota}.json` (`buildId` gömülü JSON'un `buildId` alanında).

Savaş testi: **tabii (Test)** eklentisi — katalog/detay/sezon/bölüm/dil/altyazı tamamen `__NEXT_DATA__`'dan. Görsel tabanı genelde ayrı bir CDN'dir (`cms-...-public-image...`); JS paketlerinde `"https://cms-..."` dizilerini ara, `/{name}` ile 200 döndüğünü `curl` ile doğrula.

## 3) Saf istemci SPA (veri yalnız API'de)

Gömülü JSON yoksa veri ağ geçidinden geliyordur.

1. JS paketlerini listele (`/_next/static/chunks/...`, `assets/*.js`) ve indir.
2. Paketlerde uç adı ara: tırnaklı dizeler (`"/content..."`), şablon dizeleri (`` `${basePath}/...` ``), çatı ifadeleri (`drm/v1/`, `pbr/v1/` gibi sürümlü yol parçaları). Yollar çalışma anında birleştiriliyorsa `basePath`/`config` kullanım yerlerinin ÇEVRESİNİ oku.
3. Ağ geçidi davranışını `curl` ile yokla: 404 `{"errorcode":"contentNotFound"}` = uç yanlış ama geçidi canlı; 401/403 = uç doğru olabilir ama yetki gerekli.
4. Uç adları bulunamıyorsa tarayıcı panelinde siteyi AÇ, gerçek sayfalarda URL kalıplarını (yönlendirmeler dahil) oku; `references/browser-devtools-to-provider.md`'deki ağ kaydı akışını izle.

## 4) JSON API öncelikli siteler

HTML neredeyse hiç işe yaramaz; belgelenmiş/yaygın arama uçları vardır.

- Sorgu uçlarını bul: `advancedsearch`, `metadata`, `pages` gibi.
- Sağlayıcıda `app.get(url).text` + `org.json` ile çözümle (ek bağımlılık ekleme).
- Sayfalama parametrelerini (`page`, `rows`, `offset`) katalog `hasNext`'e bağla.
Savaş testi: **ArsivSinema** — `advancedsearch.php?q=...&output=json` (katalog/arama) + `/metadata/{id}` (dosyalar: çoklu kalite MP4/WebM + SRT altyazılar).

## 5) SSR liste + AJAX/Livewire arama

Listeler düz HTML'de gelir (kazıyabilirsin), yalnız **arama** ve bazı eylemler AJAX'tır (Laravel Livewire: `wire:snapshot`, `/livewire-.../update` uçları, CSRF).

- Katalog/detay: normal yol (1).
- Arama: iki seçenek — (a) sitede arama yoksa kategorileri bir kez çekip başlıkta filtrele; (b) Livewire uçlarını taklit etmek gerekiyorsa CSRF + snapshot formatını ağ kaydından çözümle (kırılgandır; önce (a)'yı dene).
- Sayfa 404/CHALLENGE döndürürse IP engeli olabilir; bulgu notuna yaz, emülatör/telefon ağında doğrula.

## 6) DRM'li akışlar (Widevine/FPS/PlayReady)

1. Akış listelerinde `drmSchema`/`widevine`/`fps`/`playready` ve `resourceId` alanlarını ara; manifest `application/dash+xml` + `xmlns:cenc` DRM'i doğrular.
2. **Sunucuda gömülü listelerde DRM bilgisi kalır**: eklenti akış adresini `url + "#drm=" + urlencode(lisansAdresi)` biçiminde verir. Ev sahibi uygulama (bizimki) eki ayıklar, `DefaultDrmSessionManager` (Widevine L3 dahil) kurar.
3. Lisans genelde **ticket/entitlement** ister (`/drm/v1/wv?ticket=...&resource_id=...`). Boş ticket → 400 "token segments": kaynağını (misafir oturumu mu, giriş mi) bulmadan oynatma tamamlanmaz. Bu durumu `status.json`'da açıkça raporla; **"oynatma doğrulandı" deme**.
4. `drmSchema:"clear"` yayınlarda (çoğu canlı) ek gerekmez, doğrudan oynatılır.

## Genel kurallar

- Her katmanı **tek temsilciyle** doğrula: bir katalog satırı, bir dizi, bir bölüm, bir oynatma denemesi.
- Görsel/medya göreli URL'lerini mutlaklaştır; imzalı CDN adreslerini regex'te kesme (greedy al).
- Doğrulama kapıları (`verification-and-release.md`) mimariden bağımsız geçerli: paket derlendi ≠ oynatma çalıştı.