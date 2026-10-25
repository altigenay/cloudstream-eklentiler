package com.altigenay.atvdizi

import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import org.json.JSONObject
import org.jsoup.nodes.Document
import org.jsoup.nodes.Element

/**
 * ATV (www.atv.com.tr) — YAYINCININ KENDİ resmî sitesi; dizilerinin ücretsiz bölümleri.
 *
 * Mimari (bkz. references/site-architectures.md yol 1): SSR HTML kartlar +
 * bölüm sayfalarında gömülü JSON-LD VideoObject (contentUrl doğrudan MP4).
 *   katalog (/diziler, /eski-diziler) -> dizi sayfası -> {n}-bolum/izle -> MP4.
 * Fragmanlar hariç tutulur; her bölüm TEK kaynak sunar (tekil sunucu kuralı).
 * Video indirilmez; yalnızca yayıncının kendi adresi oynatıcıya verilir.
 */
class AtvDizi : MainAPI() {
    override var mainUrl = "https://www.atv.com.tr"
    override var name = "ATV Dizileri"
    override var lang = "tr"
    override val hasMainPage = true
    override val hasQuickSearch = false
    override val supportedTypes = setOf(TvType.TvSeries, TvType.Movie)

    override val mainPage = mainPageOf(
        "son" to "Son Bölümler",
        "diziler" to "Diziler",
        "eski" to "Eski Diziler",
    )

    private val bolumYolu = Regex("^/([a-z0-9-]+)/([0-9]+)-bolum/?$")
    private val diziKaraListe = setOf(
        "diziler", "eski-diziler", "canli-yayin", "yayin-akisi", "filmler", "programlar",
        "iletisim", "uye-ol", "giris-yap", "ara", "galeri", "video", "haber", "rss",
    )

    // ------------------------------------------------------------------ yardımcılar

    /** Bölüm sayfasına gömülü JSON-LD VideoObject (ad, özet, kapak, doğrudan MP4). */
    private fun videoNesnesi(html: String): JSONObject? {
        val re = Regex(
            "<script[^>]*application/ld\\+json[^>]*>(.*?)</script>",
            setOf(RegexOption.DOT_MATCHES_ALL)
        )
        for (m in re.findAll(html)) {
            runCatching {
                val d = JSONObject(m.groupValues[1].trim())
                if (d.optString("@type") == "VideoObject") return d
            }
        }
        return null
    }

    private fun gorsel(el: Element?): String? {
        val img = el?.selectFirst("img") ?: return null
        return img.absUrl("data-src").ifBlank { img.absUrl("src") }.ifBlank { null }
    }

    private fun baslikTuret(slug: String, bolum: String): String =
        slug.split("-").joinToString(" ") { it.replaceFirstChar { c -> c.uppercaseChar() } } +
            " · $bolum. Bölüm"

    /** Katalog kartları: kök yollu dizi sayfaları (/abi, /ask-ve-taht ...). */
    private fun diziOgeleri(doc: Document): List<SearchResponse> {
        val out = ArrayList<SearchResponse>()
        for (a in doc.select("a[href]")) {
            val u = a.absUrl("href").removeSuffix("/")
            if (u.isBlank() || !u.startsWith(mainUrl)) continue
            val slug = u.removePrefix(mainUrl)
            if (!slug.matches(Regex("^/[a-z0-9-]+$"))) continue
            if (slug.removePrefix("/") in diziKaraListe) continue
            val ad = a.text().trim().ifBlank { a.selectFirst("img")?.attr("alt")?.trim().orEmpty() }
            if (ad.isBlank() || ad.length < 3) continue
            out += newTvSeriesSearchResponse(ad, u, TvType.TvSeries) { posterUrl = gorsel(a) }
        }
        return out.distinctBy { it.url }
    }

    /** "Son Bölümler" kartları: {slug}/{n}-bolum/izle (fragmanlar hariç). */
    private fun sonBolumler(doc: Document): List<SearchResponse> {
        val out = ArrayList<SearchResponse>()
        for (a in doc.select("a[href*=/izle]")) {
            val yol = try {
                java.net.URI(a.absUrl("href")).path
            } catch (_: Exception) {
                continue
            }
            val m = bolumYolu.matchEntire(yol.trimEnd('/')) ?: continue
            val ad = baslikTuret(m.groupValues[1], m.groupValues[2])
            out += newMovieSearchResponse(ad, a.absUrl("href"), TvType.Movie) { posterUrl = gorsel(a) }
        }
        return out.distinctBy { it.url }
    }

    // ------------------------------------------------------------------ katalog

    override suspend fun getMainPage(page: Int, request: MainPageRequest): HomePageResponse {
        val doc = app.get(if (request.data == "son") mainUrl else "$mainUrl/${request.data}").document
        val ogeler = when (request.data) {
            "son" -> sonBolumler(doc)
            else -> diziOgeleri(doc)
        }
        return newHomePageResponse(request.name, ogeler, hasNext = false)
    }

    override suspend fun search(query: String): List<SearchResponse> {
        val q = query.trim().lowercase()
        val tumu = ArrayList<SearchResponse>()
        tumu += diziOgeleri(app.get("$mainUrl/diziler").document)
        tumu += diziOgeleri(app.get("$mainUrl/eski-diziler").document)
        tumu += sonBolumler(app.get(mainUrl).document)
        return tumu.distinctBy { it.url }.filter {
            it.name.lowercase().contains(q) || it.url.lowercase().contains(q.replace(" ", "-"))
        }
    }

    // ------------------------------------------------------------------ detay

    override suspend fun load(url: String): LoadResponse {
        val yol = runCatching { java.net.URI(url).path }.getOrDefault(url)
        val doc = app.get(url).document
        val html = doc.html()

        // Tek bölüm sayfası: JSON-LD -> doğrudan oynatma verisi
        if (bolumYolu.matchEntire(yol.trimEnd('/')) != null) {
            val v = videoNesnesi(html)
            val ad = v?.optString("name")?.ifBlank { null } ?: doc.title()
            return newMovieLoadResponse(ad, url, TvType.Movie, v?.optString("contentUrl") ?: url) {
                posterUrl = v?.optString("thumbnailUrl")?.ifBlank { null }
                plot = v?.optString("description")?.ifBlank { null }
            }
        }

        // Dizi sayfası: bölüm bağlantıları
        val diziAd = doc.selectFirst("meta[property=og:title]")?.attr("content")?.trim()
            ?.substringBefore("|")?.trim()?.ifBlank { null } ?: doc.title().substringBefore("|").trim()
        val poster = doc.selectFirst("meta[property=og:image]")?.attr("content")?.ifBlank { null }
        val ozet = doc.selectFirst("meta[property=og:description]")?.attr("content")?.ifBlank { null }
        val bolumler = ArrayList<Episode>()
        val gorulen = HashSet<String>()
        for (a in doc.select("a[href*=/izle]")) {
            val href = a.absUrl("href")
            val p = runCatching { java.net.URI(href).path }.getOrDefault("") .trimEnd('/')
            val m = bolumYolu.matchEntire(p) ?: continue
            if (!gorulen.add(href)) continue
            val no = m.groupValues[2].toIntOrNull() ?: continue
            bolumler += newEpisode(href) {
                name = "$no. Bölüm"
                season = 1
                episode = no
                posterUrl = gorsel(a) ?: poster
            }
        }
        bolumler.sortBy { it.episode ?: 0 }
        return newTvSeriesLoadResponse(diziAd, url, TvType.TvSeries, bolumler) {
            posterUrl = poster
            plot = ozet
        }
    }

    // ------------------------------------------------------------------ akış (ANLIK)

    override suspend fun loadLinks(
        data: String,
        isCasting: Boolean,
        subtitleCallback: (SubtitleFile) -> Unit,
        callback: (ExtractorLink) -> Unit
    ): Boolean {
        // data ya doğrudan MP4 (JSON-LD'den) ya da bölüm sayfası adresidir.
        var adres = data
        if (!adres.contains("/vms/") && !adres.endsWith(".mp4", true) && !adres.endsWith(".m3u8", true)) {
            val html = app.get(adres).text
            val v = videoNesnesi(html) ?: return false
            adres = v.optString("contentUrl")
        }
        if (adres.isBlank()) return false
        val tur = if (adres.endsWith(".m3u8", true)) ExtractorLinkType.M3U8 else ExtractorLinkType.VIDEO
        callback(newExtractorLink(name, "MP4", adres, tur) {
            referer = "$mainUrl/"
            quality = Qualities.P1080.value
        })
        return true
    }
}