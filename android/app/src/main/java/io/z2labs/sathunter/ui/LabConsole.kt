package io.z2labs.sathunter.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.LabState
import java.net.Inet4Address
import java.net.NetworkInterface
import kotlin.math.roundToInt

private val Term = Color(0xFF5AE08C)
private val TermDim = Color(0xFF3A8F5C)
private val TermBg = Color(0xC0050A08)

/** IPv4 addresses of the phone's interfaces that are up (Wi-Fi, USB / Ethernet, hotspot). */
fun lanAddresses(): List<String> = try {
    NetworkInterface.getNetworkInterfaces().toList()
        .filter { it.isUp && !it.isLoopback }
        .flatMap { nif -> nif.inetAddresses.toList().filterIsInstance<Inet4Address>().map { "${it.hostAddress} (${nif.name})" } }
} catch (_: Exception) {
    emptyList()
}

/**
 * Lab console (debug mode): a terminal-like panel over the waterfall, like the radar: where the
 * PC finds the phone (address, PIN), who is connected, the measurement phase and the log.
 * Drag to move, tap to fold / unfold.
 */
@Composable
fun LabConsole(lab: LabState, modifier: Modifier = Modifier) {
    var off by remember { mutableStateOf(Offset.Zero) }
    var folded by remember { mutableStateOf(false) }
    val mono = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = Term)
    val addrs = remember(lab.ips) { lanAddresses().ifEmpty { lab.ips } }
    Column(
        modifier
            .offset { IntOffset(off.x.roundToInt(), off.y.roundToInt()) }
            .widthIn(max = 340.dp)
            .background(TermBg, RoundedCornerShape(10.dp))
            .pointerInput(Unit) { detectDragGestures { c, d -> c.consume(); off += d } }
            .pointerInput(Unit) { detectTapGestures { folded = !folded } }
            .padding(horizontal = 10.dp, vertical = 6.dp),
    ) {
        Row {
            Text("▣ LAB LINK", style = mono.copy(fontWeight = FontWeight.Bold))
            Spacer(Modifier.width(8.dp))
            Text("PIN ", style = mono.copy(color = TermDim))
            Text(lab.pin, style = mono.copy(fontSize = 16.sp, fontWeight = FontWeight.Bold))
        }
        if (lab.phase.isNotEmpty()) {
            val step = if (lab.total > 0) "[${lab.step}/${lab.total}] " else ""
            Text("▶ $step${lab.phase} ${lab.detail}", style = mono.copy(color = Color(0xFFFFC83C)), maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (lab.total > 0) {
                LinearProgressIndicator(
                    progress = { lab.step.toFloat() / lab.total }, color = Color(0xFFFFC83C), trackColor = Color(0xFF1C2A20),
                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp).height(3.dp),
                )
            }
        }
        if (folded) return@Column
        if (addrs.isEmpty()) {
            Text("no LAN address: connect Wi-Fi or USB Ethernet", style = mono.copy(color = Color(0xFFFF7A6B)))
        } else {
            Text("on the PC:", style = mono.copy(color = TermDim))
            for (a in addrs) Text("  http://${a.substringBefore(' ')}:${lab.port}  ${a.substringAfter(' ', "")}", style = mono)
            Text("  python tools/lab/lab.py --phone ${addrs.first().substringBefore(' ')} --pin ${lab.pin}", style = mono.copy(fontSize = 10.sp, color = TermDim))
        }
        Text(if (lab.client.isNotEmpty()) "PC connected: ${lab.client}" else "waiting for the PC…", style = mono.copy(color = if (lab.client.isNotEmpty()) Term else TermDim))
        Spacer(Modifier.height(2.dp))
        for (l in lab.log.takeLast(8)) Text(l, style = mono.copy(fontSize = 10.sp, color = TermDim), maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}
