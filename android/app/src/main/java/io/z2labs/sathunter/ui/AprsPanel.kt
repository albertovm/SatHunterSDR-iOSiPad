package io.z2labs.sathunter.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.AprsState
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val Pkt = Color(0xFFFFC857)

/** The last APRS / AX.25 frames, newest at the bottom. */
@Composable
fun AprsPanel(a: AprsState, modifier: Modifier = Modifier) {
    val fmt = SimpleDateFormat("HH:mm:ss", Locale.US)
    Column(modifier.widthIn(max = 360.dp).background(Color(0xCC0A0F16), RoundedCornerShape(10.dp)).padding(8.dp)) {
        Text("APRS  ${a.count} frames" + if (a.badCrc > 0) ", ${a.badCrc} bad CRC" else "", color = Pkt, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        if (a.frames.isEmpty()) {
            Text("listening (NFM, AFSK 1200)...", color = Dim, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        }
        for (f in a.frames.takeLast(4)) {
            Text(
                fmt.format(Date((f.time * 1000).toLong())) + " " + f.tnc2 + if (f.lat != null) "  ⌖" else "",
                color = Color(0xFFE8E3D5), fontSize = 11.sp, fontFamily = FontFamily.Monospace, maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
