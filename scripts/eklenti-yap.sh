#!/usr/bin/env bash
# eklenti-yap: tek komutla resmi/ücretsiz bir siteden CloudStream eklentisi yapar, derler, yayınlar ve doğrular.
#
#   eklenti-yap <site-adresi> <EklentiAdi> ["ek açıklama"]
#   örnek: eklenti-yap https://www.kanald.com.tr/diziler KanalD "Diziler; videolar Kanal D'nin resmi YouTube kanalından"
#
# Ortam değişkenleri:
#   EKLENTI_MODEL=sağlayıcı/model   OpenCode'un kullanacağı model (boşsa OpenCode varsayılanı)
#   EKLENTI_PUSH=0                  GitHub'a gönderme, sadece yerelde derle
#
# Kurallar: yalnızca resmi ve ücretsiz kaynaklar (KAYNAK-REHBERI.md). Korsan site belirtisi görülürse durur;
# 🔴 listedeki çözücüler ve CloudStream Builder becerisi kullanılmaz; asıl işi "cloudstream-eklenti" becerisiyle OpenCode yapar.
set -euo pipefail

DEPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
OPENCODE="${OPENCODE:-$HOME/.opencode/bin/opencode}"
URL="${1:-}"; AD="${2:-}"; NOT="${3:-}"
MAX_DENEME=3
renk() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
adim() { renk "1;36" "▶ $*"; }
tamam() { renk "1;32" "✔ $*"; }
dur() { renk "1;31" "✖ $*"; exit 1; }

[[ -n "$URL" && -n "$AD" ]] || { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
[[ "$AD" =~ ^[A-Z][A-Za-z0-9]+$ ]] || dur "Eklenti adı büyük harfle başlamalı, sadece harf/rakam: ör. KanalD"
[[ "$URL" =~ ^https?:// ]] || dur "Site adresi http(s):// ile başlamalı"
command -v "$OPENCODE" >/dev/null || [[ -x "$OPENCODE" ]] || dur "OpenCode bulunamadı ($OPENCODE)"
ALAN="$(printf '%s' "$URL" | sed -E 's#^https?://([^/]+).*#\1#')"
KOK="$(printf '%s' "$URL" | sed -E 's#^(https?://[^/]+).*#\1#')"
PAKET="$(printf '%s' "$AD" | tr '[:upper:]' '[:lower:]')"

# ── 1. Ön kontrol: korsan site belirtisi, robots.txt
adim "1/6 Kaynak kontrolü: $ALAN"
if printf '%s' "$ALAN" | grep -qiE 'film-?izle|dizi-?izle|hdfilm|fullhd|filmmakinesi|filmcehennemi|dizibox|dizipal|dizimom|setfilm|netfilm|sinemakolik|jetfilm|yabancidizi|anizm|turkanime|\.(fat|top|pro|cfd|sbs|lol|click)$'; then
  dur "Alan adı izinsiz film/dizi sitelerine benziyor ($ALAN). Bu araç yalnızca resmi/ücretsiz kaynaklar içindir (bkz. KAYNAK-REHBERI.md)."
fi
SAYFA="$(curl -sL -m 25 -A 'Mozilla/5.0' "$URL" || true)"
[[ -n "$SAYFA" ]] || dur "Site açılmadı: $URL"
if printf '%s' "$SAYFA" | grep -qiE 'full hd film izle|bedava film izle|film izle - |dizi izle - |altyazılı film izle'; then
  dur "Sayfa içeriği izinsiz film/dizi sitesine benziyor. Durduruldu."
fi
ROBOTS="$(curl -sL -m 15 "$KOK/robots.txt" || true)"
YOL="$(printf '%s' "$URL" | sed -E 's#^https?://[^/]+##')"; YOL="${YOL:-/}"
if printf '%s\n' "$ROBOTS" | awk 'BEGIN{IGNORECASE=1} /^user-agent:[[:space:]]*\*/{a=1;next} /^user-agent:/{a=0} a && /^disallow:[[:space:]]*\/[[:space:]]*$/{f=1} END{exit !f}'; then
  dur "robots.txt tüm siteyi yasaklıyor; eklenti yapılmaz."
fi
tamam "Belirgin bir sorun yok. Son karar senin: içerik sahibinin kendi sitesi mi, ücretsiz mi?"

# ── 2. İskelet: TrtBelgesel örneğinden
adim "2/6 İskelet: $AD/"
cd "$DEPO"
git pull -q --rebase || true
if [[ -d "$AD" ]]; then
  tamam "$AD/ zaten var; üzerinde çalışılacak (sürüm artırılacak)"
else
  mkdir -p "$AD/src/main/kotlin/com/altigenay/$PAKET"
  cp TrtBelgesel/src/main/AndroidManifest.xml "$AD/src/main/"
  cat > "$AD/build.gradle.kts" <<EOF
version = 1

cloudstream {
    description = "$AD ($ALAN)"
    authors = listOf("altigenay")
    status = 1
    tvTypes = listOf("TvSeries")
    language = "tr"
    iconUrl = "$KOK/favicon.ico"
}
EOF
  cat > "$AD/src/main/kotlin/com/altigenay/$PAKET/${AD}Plugin.kt" <<EOF
package com.altigenay.$PAKET

import android.content.Context
import com.lagradost.cloudstream3.plugins.CloudstreamPlugin
import com.lagradost.cloudstream3.plugins.Plugin

@CloudstreamPlugin
class ${AD}Plugin : Plugin() {
    override fun load(context: Context) {
        registerMainAPI($AD())
    }
}
EOF
  sed -e "s/package com.altigenay.trtbelgesel/package com.altigenay.$PAKET/" \
      -e "s/class TrtBelgesel : MainAPI/class $AD : MainAPI/" \
      TrtBelgesel/src/main/kotlin/com/altigenay/trtbelgesel/TrtBelgesel.kt \
      > "$AD/src/main/kotlin/com/altigenay/$PAKET/$AD.kt"
  tamam "TrtBelgesel kopyalandı; site için uyarlanacak"
fi

# ── 3. Asıl iş: OpenCode + cloudstream-eklenti becerisi
GOREV="cloudstream-eklenti becerisini kullan (KULLANIM.md ve KAYNAK-REHBERI.md kurallarına uy).
Görev: $DEPO deposundaki $AD/ eklentisini $URL sitesi için yaz. ${NOT:+Ek bilgi: $NOT.}
- $AD/src/main/kotlin/com/altigenay/$PAKET/$AD.kt dosyası TrtBelgesel'in kopyası; mainUrl, name, mainPage, getMainPage, search, load ve loadLinks'i bu siteye göre yeniden yaz. Bu siteye ait olmayan TRT parçalarını (kategoriler, canlı yayın) kaldır.
- Önce siteyi curl + Python (BeautifulSoup) ile incele; liste, detay/bölüm ve video kaynağını bul. Seçicileri canlı sitede doğrula (kaç öğe, bir bölümün video adresi).
- Video yalnızca resmi kaynaktan: kanalın resmi YouTube videosu (loadExtractor) ya da sitenin kendi şifresiz resmi HLS akışı. DRM, üyelik, reklam ya da bölge kısıtı atlatma YOK. extractors/ klasöründeki 🔴 çözücüleri ve kökteki SKILL.md'yi (CloudStream Builder) KULLANMA.
- Site izinsiz içerik yayınlıyorsa ya da video sadece reklam/DRM atlatılarak alınabiliyorsa kod yazma; nedenini yaz ve dur.
- $AD/build.gradle.kts içindeki description ve tvTypes'ı düzelt; dosya zaten vardıysa version'ı 1 artır.
- Sonunda ./gradlew $AD:make ile derle; hata varsa düzelt. git commit/push YAPMA (script yapacak).
- En sonda kısa bir özet yaz: kaç kategori/dizi/bölüm bulundu, video nereden geliyor, neyi doğrulayamadın."
adim "3/6 OpenCode eklentiyi yazıyor (birkaç dakika sürebilir)…"
MODEL_ARG=(); [[ -n "${EKLENTI_MODEL:-}" ]] && MODEL_ARG=(-m "$EKLENTI_MODEL")
"$OPENCODE" run "${MODEL_ARG[@]}" --dir "$DEPO" "$GOREV"

# ── 4. Derleme (hata varsa OpenCode'a geri ver)
adim "4/6 Derleme"
for ((i=1; i<=MAX_DENEME; i++)); do
  if HATA="$(./gradlew -q "$AD:make" 2>&1)"; then tamam "$AD/build/$AD.cs3 oluştu"; break; fi
  (( i == MAX_DENEME )) && { printf '%s\n' "$HATA" | grep -E '^e:|wrong' | head -20; dur "Derleme $MAX_DENEME denemede düzelmedi"; }
  renk "1;33" "Derleme hatası, OpenCode düzeltiyor (deneme $i/$MAX_DENEME)…"
  "$OPENCODE" run "${MODEL_ARG[@]}" --dir "$DEPO" "cloudstream-eklenti becerisini kullan. $AD eklentisi derlenmiyor, düzelt (commit/push yapma). Hatalar:
$(printf '%s\n' "$HATA" | grep -E '^e:|wrong|error' | head -30)"
done
[[ -s "$AD/build/$AD.cs3" ]] || dur "$AD.cs3 oluşmadı"

# ── 5. Yerel denetim (depodaki güvenli araçlar)
adim "5/6 Kod denetimi"
python3 scripts/audit_provider_contracts.py "$AD" 2>/dev/null | tail -15 || renk "1;33" "audit_provider_contracts çalışmadı (atlandı)"

if [[ "${EKLENTI_PUSH:-1}" == "0" ]]; then
  tamam "Yerel derleme hazır: $DEPO/$AD/build/$AD.cs3 (EKLENTI_PUSH=0, gönderilmedi)"; exit 0
fi

# ── 6. Yayınla ve kurulum zincirini doğrula
adim "6/6 GitHub'a gönderiliyor ve doğrulanıyor"
git add "$AD"
git commit -qm "$AD eklentisi ($ALAN)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || tamam "Değişiklik yok"
git pull -q --rebase && git push -q
sleep 15
for ((i=0; i<60; i++)); do
  DURUM="$(gh run list -R altigenay/cloudstream-eklentiler -L 1 --json status,conclusion -q '.[0].status+" "+.[0].conclusion')"
  [[ "$DURUM" == completed* ]] && break; sleep 10
done
[[ "$DURUM" == "completed success" ]] || { gh run view -R altigenay/cloudstream-eklentiler --log-failed 2>/dev/null | tail -20; dur "GitHub derlemesi başarısız: $DURUM"; }
tamam "GitHub derlemesi başarılı"
node scripts/verify_remote_repo.mjs "https://raw.githubusercontent.com/altigenay/cloudstream-eklentiler/main/repo.json" 2>&1 | tail -8 || true
curl -s "https://raw.githubusercontent.com/altigenay/cloudstream-eklentiler/builds/plugins.json" | grep -q "\"internalName\": \"$AD\"" \
  && tamam "$AD depoda yayında. Telefonda: CloudStream → Eklentiler → depo → güncelle → $AD" \
  || dur "$AD plugins.json içinde görünmüyor"
renk "1;33" "Not: Derleme ve yayın doğrulandı; oynatmayı telefonda dene. Çalışmazsa: eklenti-yap $URL $AD \"şu çalışmıyor: …\""
