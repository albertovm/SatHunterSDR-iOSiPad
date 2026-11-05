package io.z2labs.sathunter.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.BuildConfig
import io.z2labs.sathunter.Engine
import io.z2labs.sathunter.Status
import io.z2labs.sathunter.Updater
import androidx.compose.runtime.collectAsState

@Composable
private fun Section(title: String) {
    Text(title, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = Accent, modifier = Modifier.padding(top = 14.dp, bottom = 4.dp))
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    st: Status,
    engine: Engine,
    updater: Updater,
    compassOn: Boolean,
    onCompass: (Boolean) -> Unit,
    gpsInfo: String,
    onFollowGps: (Boolean) -> Unit,
    guardMin: Int = 2,
    onGuard: (Int) -> Unit = {},
) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 8.dp)) {
        Section("Receiver")
        Text("Source", fontSize = 14.sp)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for ((id, name) in listOf("demo" to "Demo", "rtl" to "RTL-SDR", "esp" to "ESP-SDR (ESP32-S3)")) {
                FilterChip(
                    selected = st.source == id, onClick = { engine.source(id) }, enabled = id == "demo" || id in st.devices,
                    label = { Text(name) },
                )
            }
        }
        Text(
            if (st.sourceStatus.isNotEmpty()) st.sourceStatus else "Plug in an RTL-SDR or an ESP32-S3 (its native USB port) with an OTG cable.",
            color = Dim, fontSize = 12.sp,
        )
        Text("Sample rate", fontSize = 14.sp, modifier = Modifier.padding(top = 8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for (r in st.rates.ifEmpty { listOf(2_400_000.0, 2_048_000.0, 1_024_000.0, 250_000.0) }) {
                FilterChip(selected = st.rate == r, onClick = { engine.rate(r) }, label = { Text(if (r >= 1e6) "%.3f MS/s".format(r / 1e6) else "%.1f kS/s".format(r / 1e3)) })
            }
        }
        if (st.source != "esp") {
            // Like SDR++'s decimation: a narrower span with finer FFT bins and less CPU
            Text("Decimation", fontSize = 14.sp, modifier = Modifier.padding(top = 8.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                for (d in listOf(1, 2, 4, 8)) {
                    val span = st.rate / d
                    val label = if (d == 1) "Off" else "/$d · " + if (span >= 1e6) "%.1f MHz".format(span / 1e6) else "%.0f kHz".format(span / 1e3)
                    FilterChip(selected = st.decimation == d, onClick = { engine.decimation(d) }, label = { Text(label) })
                }
            }
            Text("Narrows the spectrum around the VFO: weak beacons stand out more, the phone works less.", color = Dim, fontSize = 12.sp)
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            Column(Modifier.weight(1f)) {
                Text("Center tuning", fontSize = 14.sp)
                Text("The VFO stays in the middle, tuning moves the whole spectrum", color = Dim, fontSize = 12.sp)
            }
            Switch(checked = st.centerTuning, onCheckedChange = { engine.centerTuning(it) })
        }
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            Text("Automatic gain", Modifier.weight(1f), fontSize = 14.sp)
            Switch(checked = st.gain == null, onCheckedChange = { engine.gain(if (it) null else if (st.source == "esp") 60.0 else 32.8) })
        }
        if (st.gain != null) {
            var g by remember(st.gain) { mutableFloatStateOf(st.gain.toFloat()) }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("%.1f dB".format(g), Modifier.width(70.dp), fontSize = 14.sp)
                val gmax = (st.gains.maxOrNull() ?: 49.6).toFloat().coerceAtLeast(1f)
                Slider(value = g.coerceIn(0f, gmax), onValueChange = { g = it }, valueRange = 0f..gmax, onValueChangeFinished = { engine.gain(g.toDouble()) })
            }
        }
        if (st.hasBiasTee) {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                Column(Modifier.weight(1f)) {
                    Text("Bias tee (4.5 V to the antenna)", fontSize = 14.sp)
                    Text(
                        "Powers an LNA or active antenna through the coax. Only switch it on when one is connected: a DC-shorted antenna or a device without a DC block can be damaged.",
                        color = Dim, fontSize = 12.sp,
                    )
                }
                Switch(checked = st.biasTee, onCheckedChange = { engine.biasTee(it) })
            }
            // Crystal correction: an RTL-SDR is often 1-2 ppm off, ~0.5-1 kHz at 435 MHz,
            // enough to put a CW beacon outside its filter
            var ppmText by remember(st.ppm) { mutableStateOf("%.1f".format(st.ppm)) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                OutlinedTextField(ppmText, { ppmText = it }, label = { Text("Frequency correction (ppm)") }, singleLine = true, modifier = Modifier.weight(1f),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                Button(onClick = { ppmText.replace(',', '.').toDoubleOrNull()?.let { engine.ppm(it) } }) { Text("Set") }
            }
            Text("Tune to a known signal; if it shows X Hz too high at F MHz, enter X / F (e.g. +600 Hz at 435 MHz = 1.4).", color = Dim, fontSize = 12.sp)
        }
        Text("FFT size", fontSize = 14.sp, modifier = Modifier.padding(top = 8.dp))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for (n in listOf(2048, 4096, 8192, 16384)) {
                FilterChip(selected = st.bins == n, onClick = { engine.fft(n) }, label = { Text("$n") })
            }
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Ground station")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Follow the phone's GPS", Modifier.weight(1f), fontSize = 14.sp)
            Switch(checked = st.followGps, onCheckedChange = onFollowGps)
        }
        if (st.followGps && gpsInfo.isNotEmpty()) Text(gpsInfo, color = Dim, fontSize = 12.sp)
        var lat by remember(st.lat) { mutableStateOf("%.5f".format(st.lat)) }
        var lon by remember(st.lon) { mutableStateOf("%.5f".format(st.lon)) }
        var alt by remember(st.altM) { mutableStateOf("%.0f".format(st.altM)) }
        var loc by remember(st.locator) { mutableStateOf(st.locator) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(lat, { lat = it }, label = { Text("Latitude") }, singleLine = true, modifier = Modifier.weight(1f),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
            OutlinedTextField(lon, { lon = it }, label = { Text("Longitude") }, singleLine = true, modifier = Modifier.weight(1f),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(alt, { alt = it }, label = { Text("Altitude m") }, singleLine = true, modifier = Modifier.weight(1f),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number))
            Button(onClick = {
                val la = lat.replace(',', '.').toDoubleOrNull()
                val lo = lon.replace(',', '.').toDoubleOrNull()
                if (la != null && lo != null) engine.station(la, lo, alt.toDoubleOrNull())
            }) { Text("Set") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(loc, { loc = it }, label = { Text("Maidenhead locator") }, singleLine = true, modifier = Modifier.weight(1f))
            Button(onClick = { engine.locator(loc) }) { Text("Set") }
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Decoders")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("APRS / packet (AFSK 1200, AX.25)", fontSize = 14.sp)
                Text("ISS digipeater on 145.825 MHz and APRS CubeSats, in NFM. The frames show in a panel on the receiver screen.", color = Dim, fontSize = 12.sp)
            }
            Switch(checked = st.aprs.on, onCheckedChange = { engine.aprs(it) })
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Decoder plugins", fontSize = 14.sp)
                Text("Small Luau scripts turn the decoded frames into readable lines and map positions (ISS APRS, generic APRS).", color = Dim, fontSize = 12.sp)
            }
            Switch(checked = st.pluginsOn, onCheckedChange = { engine.plugins(it) })
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("SSTV pictures (Robot 36, PD120)", fontSize = 14.sp)
                Text("ISS SSTV events on 145.800 MHz, in NFM. The picture builds up in a panel on the receiver screen.", color = Dim, fontSize = 12.sp)
            }
            Switch(checked = st.sstv.on, onCheckedChange = { engine.sstv(it) })
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Screen")
        Text("Screen saver (protects an AMOLED screen during long passes and measurements)", fontSize = 14.sp)
        Text("After this long without a touch the screen goes black and dim; a small summary (frequency, satellite, signal, lab phase, last decode, battery) moves around so no pixel stays lit. The receiver keeps running; tap to wake.",
            color = Dim, fontSize = 12.sp)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            for ((m, label) in listOf(0 to "Off", 1 to "1 min", 2 to "2 min", 5 to "5 min", 10 to "10 min")) {
                FilterChip(selected = guardMin == m, onClick = { onGuard(m) }, label = { Text(label) })
            }
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Debug")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Debug mode (lab link)", fontSize = 14.sp)
                Text(
                    "Measurements over the LAN: a PC on the same Wi-Fi or USB Ethernet drives a signal generator and reads the receiver (tools/lab/lab.py). The lab console on the receiver screen shows the address and the PIN.",
                    color = Dim, fontSize = 12.sp,
                )
            }
            Switch(checked = st.debugMode, onCheckedChange = { engine.debugMode(it) })
        }
        var pin by remember(st.labPin) { mutableStateOf(st.labPin) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(pin, { pin = it.filter(Char::isDigit).take(8) }, label = { Text("Lab PIN (4-8 digits, empty = random)") }, singleLine = true,
                modifier = Modifier.weight(1f), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword))
            Button(onClick = { engine.labPin(pin) }) { Text("Set") }
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Radar")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Compass (turn the radar with the phone, aim at the satellite)", Modifier.weight(1f), fontSize = 14.sp)
            Switch(checked = compassOn, onCheckedChange = onCompass)
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("Updates")
        val upd by updater.state.collectAsState()
        var pre by remember { mutableStateOf(updater.includePrerelease) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Beta and lab builds too", Modifier.weight(1f), fontSize = 14.sp)
            Switch(checked = pre, onCheckedChange = { pre = it; updater.includePrerelease = it })
        }
        Text(updateText(upd), color = Dim, fontSize = 12.sp)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { updater.check(pre) }) { Text("Check now") }
            (upd as? Updater.State.Available)?.let { a -> Button(onClick = { updater.install(a.rel) }) { Text("Install ${a.rel.tag}") } }
        }

        HorizontalDivider(Modifier.padding(top = 12.dp))
        Section("About")
        Text("SatHunterSDR ${BuildConfig.VERSION_NAME} (${BuildConfig.GIT_REV})", fontSize = 14.sp)
        Text("Z2Labs · GPL-3.0-or-later · github.com/z2labs/SatHunter-SDR", color = Dim, fontSize = 12.sp)
        Text("Satellite data: SatNOGS DB (CC BY-SA 4.0), CelesTrak.", color = Dim, fontSize = 12.sp)
    }
}
