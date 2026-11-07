package io.z2labs.sathunter.ui

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * A panel over the waterfall (lab console, SSTV, APRS) that folds into a one-line chip, so it does
 * not hide the signals. Folded by default; a tap on the chip opens it, a tap on its title folds it.
 * The state is remembered per panel. With `onClose`, a ✕ switches the decoder off.
 */
@Composable
fun Fold(
    key: String,
    title: String,
    summary: String,
    color: Color,
    modifier: Modifier = Modifier,
    alignEnd: Boolean = false,
    onClose: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    val prefs = LocalContext.current.getSharedPreferences("ui", Context.MODE_PRIVATE)
    var open by remember { mutableStateOf(prefs.getBoolean("fold_$key", false)) }
    fun toggle() {
        open = !open
        prefs.edit().putBoolean("fold_$key", open).apply()
    }
    Column(modifier, horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start) {
        Row(
            Modifier.background(Color(0xB30A0F16), RoundedCornerShape(8.dp)),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                (if (open) "▾ " else "▸ ") + title + if (summary.isNotEmpty()) "  ·  $summary" else "",
                color = color, fontSize = 11.sp, fontFamily = FontFamily.Monospace, maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.widthIn(max = 280.dp).clickable { toggle() }.padding(start = 8.dp, end = 6.dp, top = 6.dp, bottom = 6.dp),
            )
            // ✕ switches the decoder off (Settings switches it on again)
            if (onClose != null) {
                Text(
                    "✕", color = Color(0xFFB0B8C0), fontSize = 13.sp,
                    modifier = Modifier.clickable { onClose() }.padding(start = 4.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),
                )
            }
        }
        if (open) content()
    }
}
