package io.z2labs.sathunter

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Settings

/**
 * After an update of the app (a silent self-update from the lab link, overnight) bring the app
 * back, so the receiver and the lab link run again without anyone opening it. Android lets a
 * background app start an activity only with "Display over other apps"; without it nothing happens.
 */
class ReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        if (!Settings.canDrawOverlays(ctx)) return
        ctx.startActivity(Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
