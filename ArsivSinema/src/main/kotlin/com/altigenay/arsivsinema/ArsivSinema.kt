package com.altigenay.arsivsinema

import com.lagradost.cloudstream3.*
import com.lagradost.cloudstream3.utils.*
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLEncoder

/**
 * ArsivSinema — TEST eklentisi: Internet Archive'deki KAMUYA AÇIK / telifi düşmüş filmler.
 *
 * Amaç: oynatıcı ve .cs3 eklenti motorunun (katalog → detay → çoklu kalite → altyazı →
 * oynatma) gerçek veriyle, YASAL kaynaktan test edilmesi. Video indirilmez; yalnızca
 * arşivdeki resmi dosya adresleri oynatıcıya verilir.
 */
class ArsivSinema : MainAPI() {
    override var mainUrl = "https://archive.org"
    override var name = "ArsivSinema (Test)"
    override var lang = "en"
    override val hasMainPage = true
    override val hasQuickSearch = false
    override val supportedTypes = setOf(TvType.Movie, TvType.Documentary)

    override val mainPage = mainPageOf(
        "feature_films" to "Klasik Filmler",
        "classic_cartoons" to "Klasik Çizgi Filmler",
        "SciFi" to "Bilim Kurgu Arşivi",
        "Film_Noir" to "Film Noir",
        "silentfilms" to "Sessiz Filmler",
        "classic_tv" to "Klasik TV",
    )

    private fun kimlik(url: String): String =
        url.substringAfter("/details/", "").substringBefore("?").substringBefore("#").trim('/')
            .ifBlank { url.substringAfterLast('/') }

    private fun poster(id: String) = "$mainUrl/services/img/$id"

    private fun araUrl(sorgu: String, sayfa: Int): String =
        "$mainUrl/advancedsearch.php?q=" + URLEncoder.encode(sorgu, "UTF-8") +
            "&fl[]=identifier&fl[]=title&fl[]=year&rows=40&page=$sayfa&output=json"

    private fun ogeleri(json: String): List<SearchResponse> {
        val out = ArrayList<SearchResponse>()
        val docs = JSONObject(json).optJSONObject("response")?.optJSONArray("docs") ?: return out
        for (i in 0 until docs.length()) {
            val d = docs.optJSONObject(i) ?: continue
            val id = d.optString("identifier")
            if (id.isBlank()) continue
            val ad = d.optString("title").ifBlank { id }
            val yil = d.optString("year").take(4).toIntOrNull()
            out += newMovieSearchResponse(ad, "$mainUrl/details/$id", TvType.Movie) {
                posterUrl = poster(id)
                this.year = yil
            }
        }
        return out
    }

    override suspend fun getMainPage(page: Int, request: MainPageRequest): HomePageResponse {
        val json = app.get(araUrl("collection:(${request.data}) AND mediatype:(movies)", page)).text
        return newHomePageResponse(request.name, ogeleri(json), hasNext = true)
    }

    override suspend fun search(query: String): List<SearchResponse> =
        ogeleri(app.get(araUrl("($query) AND mediatype:(movies)", 1)).text)

    override suspend fun load(url: String): LoadResponse {
        val id = kimlik(url)
        val kok = JSONObject(app.get("$mainUrl/metadata/$id").text)
        val m = kok.optJSONObject("metadata") ?: JSONObject()
        val ad = m.optString("title").ifBlank { id }
        val yil = m.optString("year").take(4).toIntOrNull()
        val ozet = when (val d = m.opt("description")) {
            is String -> d
            is JSONArray -> (0 until d.length()).joinToString("\n") { d.optString(it) }
            else -> null
        }
        return newMovieLoadResponse(ad, url, TvType.Movie, url) {
            posterUrl = poster(id)
            plot = ozet
            this.year = yil
        }
    }

    override suspend fun loadLinks(
        data: String,
        isCasting: Boolean,
        subtitleCallback: (SubtitleFile) -> Unit,
        callback: (ExtractorLink) -> Unit
    ): Boolean {
        val id = kimlik(data)
        val kok = JSONObject(app.get("$mainUrl/metadata/$id").text)
        val files = kok.optJSONArray("files") ?: return false
        var bulundu = false
        for (i in 0 until files.length()) {
            val f = files.optJSONObject(i) ?: continue
            val ad = f.optString("name")
            if (ad.isBlank()) continue
            val adres = "$mainUrl/download/$id/" + ad.split("/").joinToString("/") {
                URLEncoder.encode(it, "UTF-8").replace("+", "%20")
            }
            val bicim = f.optString("format")
            when {
                ad.endsWith(".srt", true) || bicim.contains("SRT", true) || bicim.contains("SubRip", true) -> {
                    val dil = Regex("[_.\\-](tr|en|es|fr|de|it|ru)([_.\\-]|$)", RegexOption.IGNORE_CASE)
                        .find(ad)?.groupValues?.get(1)?.lowercase() ?: "en"
                    subtitleCallback(newSubtitleFile(dil, adres))
                }
                ad.endsWith(".mp4", true) || ad.endsWith(".webm", true) ||
                    bicim.contains("MPEG4", true) || bicim.contains("h.264", true) ||
                    bicim.contains("WebM", true) -> {
                    val yukseklik = f.optInt("height")
                    val kalite = when {
                        yukseklik >= 1000 -> Qualities.P1080.value
                        yukseklik >= 700 -> Qualities.P720.value
                        yukseklik >= 440 -> Qualities.P480.value
                        yukseklik > 0 -> Qualities.P360.value
                        else -> Qualities.Unknown.value
                    }
                    callback(newExtractorLink(name, bicim.ifBlank { "Video" }, adres, ExtractorLinkType.VIDEO) {
                        referer = "$mainUrl/"
                        quality = kalite
                    })
                    bulundu = true
                }
            }
        }
        return bulundu
    }
}