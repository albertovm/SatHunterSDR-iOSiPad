package io.z2labs.sathunter.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.SstvState

/** The SSTV picture as it comes in (tap to enlarge / shrink). */
@Composable
fun SstvPanel(s: SstvState, pic: Bitmap?, modifier: Modifier = Modifier) {
    var big by remember { mutableStateOf(false) }
    Column(modifier.background(Color(0xCC0A0F16), RoundedCornerShape(10.dp)).padding(6.dp).clickable { big = !big }) {
        val head = when {
            s.mode != null -> "SSTV ${s.mode}  ${s.rows}/${s.height}"
            s.count > 0 -> "SSTV  ${s.count} picture" + (if (s.count > 1) "s" else "")
            else -> "SSTV  waiting for a VIS header (FM)..."
        }
        Text(head, color = Color(0xFF7FD4FF), fontSize = 11.sp, fontFamily = FontFamily.Monospace)
        pic?.let {
            Image(
                it.asImageBitmap(), null,
                Modifier.width(if (big) 320.dp else 160.dp).padding(top = 4.dp),
                contentScale = ContentScale.FillWidth, filterQuality = FilterQuality.Low,
            )
        }
    }
}
