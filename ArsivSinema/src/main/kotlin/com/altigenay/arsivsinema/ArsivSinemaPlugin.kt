package com.altigenay.arsivsinema

import android.content.Context
import com.lagradost.cloudstream3.plugins.CloudstreamPlugin
import com.lagradost.cloudstream3.plugins.Plugin

@CloudstreamPlugin
class ArsivSinemaPlugin : Plugin() {
    override fun load(context: Context) {
        registerMainAPI(ArsivSinema())
    }
}