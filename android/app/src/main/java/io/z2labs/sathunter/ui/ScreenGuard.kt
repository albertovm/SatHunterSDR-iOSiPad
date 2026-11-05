package io.z2labs.sathunter.ui

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.view.WindowManager
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.SatDetail
import io.z2labs.sathunter.Status
import kotlinx.coroutines.delay
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.random.Random

/**
 * AMOLED burn-in guard for long measurements and passes: after `minutes` without a touch the
 * screen goes black and dim, and a small grey summary (frequency, satellite, signal, lab phase,
 * last decode, battery) drifts to a new place every 20 s so no pixel stays lit. A tap wakes it.
 * The receiver, the decoders and the lab link keep running underneath.
 *
 * Wrap the whole app in it: touches pass through to the content (they only reset the timer).
 */
@Composable
fun ScreenGuard(minutes: Int, st: Status, detail: SatDetail?, content: @Composable () -> Unit) {
    var lastTouch by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var asleep by remember { mutableStateOf(false) }
    val activity = LocalContext.current as? Activity

    LaunchedEffect(minutes, lastTouch) {
        asleep = false
        if (minutes <= 0) return@LaunchedEffect
        delay(minutes * 60_000L)
        asleep = true
    }
    // Dim the backlight while asleep, back to the system setting when awake
    DisposableEffect(asleep) {
        activity?.window?.let { w ->
            val lp = w.attributes
            lp.screenBrightness = if (asleep) 0.01f else WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
            w.attributes = lp
        }
        onDispose {}
    }

    Box(
        Modifier.fillMaxSize().pointerInput(Unit) {
            // Watch every touch on its way down without taking it from the content
            awaitEachGesture {
                awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
                lastTouch = System.currentTimeMillis()
            }
        },
    ) {
        content()
        if (asleep) Saver(st, detail) { lastTouch = System.currentTimeMillis() }
    }
}

private val Grey = Color(0x66B0B8C0) // dim: little light per pixel
private val GreyHi = Color(0x88D0D6DC)

@Composable
private fun Saver(st: Status, detail: SatDetail?, onWake: () -> Unit) {
    val ctx = LocalContext.current
    var pos by remember { mutableStateOf(Pair(0.3f, 0.3f)) }
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) {
        while (true) {
            pos = Pair(Random.nextFloat(), Random.nextFloat())
            repeat(20) {
                now = System.currentTimeMillis()
                delay(1000)
            }
        }
    }
    BoxWithConstraints(
        Modifier.fillMaxSize().background(Color.Black).pointerInput(Unit) {
            awaitEachGesture {
                awaitFirstDown(requireUnconsumed = false)
                onWake()
            }
        },
    ) {
        val boxW = 260.dp
        val boxH = 150.dp
        val x = ((maxWidth - boxW).coerceAtLeast(0.dp) * pos.first)
        val y = ((maxHeight - boxH).coerceAtLeast(0.dp) * pos.second)
        Column(Modifier.offset { IntOffset(x.roundToPx(), y.roundToPx()) }.width(boxW)) {
            val t = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date(now))
            Text(t, color = GreyHi, fontSize = 22.sp, fontFamily = FontFamily.Monospace)
            Text(
                "%.4f MHz %s".format(st.vfoHz / 1e6, st.mode) + if (st.running) "" else "  (stopped)",
                color = Grey, fontSize = 13.sp, fontFamily = FontFamily.Monospace,
            )
            Text("signal %.0f dB".format(st.levelDb) + if (st.dropped > 0) "  dropped ${st.dropped}" else "", color = Grey, fontSize = 12.sp, fontFamily = FontFamily.Monospace)
            detail?.let { d ->
                val el = d.el?.let { "  el %.0f°".format(it) } ?: ""
                val dop = if (d.tracking) "  Doppler %+.0f Hz".format(d.dopplerHz) else ""
                Text(d.name + el + dop, color = Grey, fontSize = 12.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
            }
            st.lab?.let { l ->
                val prog = if (l.total > 0) " ${l.step}/${l.total}" else ""
                Text("lab: ${l.phase}$prog ${l.detail}".trim(), color = Grey, fontSize = 12.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
                l.log.lastOrNull()?.let { Text(it, color = Grey, fontSize = 11.sp, fontFamily = FontFamily.Monospace, maxLines = 1) }
            }
            st.recording?.let { r -> Text("REC %.0f s".format(r.secs), color = Grey, fontSize = 12.sp, fontFamily = FontFamily.Monospace) }
            if (st.aprs.on) {
                val last = st.plugins.lastOrNull() ?: st.aprs.frames.lastOrNull()?.tnc2
                Text("APRS ${st.aprs.count}" + (last?.let { ": $it" } ?: ""), color = Grey, fontSize = 11.sp, fontFamily = FontFamily.Monospace, maxLines = 1)
            }
            battery(ctx)?.let { Text(it, color = Grey, fontSize = 11.sp, fontFamily = FontFamily.Monospace) }
            Text("tap to wake", color = Color(0x40B0B8C0), fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        }
    }
}

/** "battery 83 % charging" from the sticky battery broadcast (no receiver needed). */
private fun battery(ctx: Context): String? {
    val i: Intent = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return null
    val level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
    val scale = i.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
    if (level < 0 || scale <= 0) return null
    val plugged = i.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) != 0
    return "battery ${level * 100 / scale} %" + if (plugged) " charging" else ""
}
