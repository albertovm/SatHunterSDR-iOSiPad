package io.z2labs.sathunter.ui

import android.content.Context
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import io.z2labs.sathunter.Engine
import io.z2labs.sathunter.Pin
import io.z2labs.sathunter.SatDetail
import io.z2labs.sathunter.Status
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.PI
import kotlin.math.acos
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.floor
import kotlin.math.sin

/** Natural Earth 1:110m land polygons (public domain), packed by tools/make_land.py: rings of (lon, lat). */
private object Land {
    private var rings: List<FloatArray>? = null

    fun get(ctx: Context): List<FloatArray> = rings ?: run {
        val b = ByteBuffer.wrap(ctx.assets.open("land110.bin").use { it.readBytes() }).order(ByteOrder.LITTLE_ENDIAN)
        val n = b.short.toInt() and 0xffff
        val r = List(n) {
            val m = b.short.toInt() and 0xffff
            FloatArray(2 * m) { b.short / 100f }
        }
        rings = r
        r
    }
}

private val LandFill = Color(0xFF1B2733)
private val LandEdge = Color(0xFF34485C)
private val Grid = Color(0xFF16202A)
private val Sea = Color(0xFF0A0F16)
private val PinCol = Color(0xFFFFC857)
private const val R_EARTH = 6371.0

/** The stations a map shows: plugin pins, or the decoded APRS positions when the plugins are off. */
fun mapPins(st: Status): List<Pin> =
    if (st.pins.isNotEmpty()) st.pins
    else st.aprs.frames.filter { it.lat != null && it.lon != null }
        .associateBy { it.src }.values.map { Pin(it.lat!!, it.lon!!, it.src, it.time) }

/** Great-circle distance, km. */
fun distanceKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
    val r = PI / 180
    val c = sin(lat1 * r) * sin(lat2 * r) + cos(lat1 * r) * cos(lat2 * r) * cos((lon2 - lon1) * r)
    return R_EARTH * acos(c.coerceIn(-1.0, 1.0))
}

/** Full-screen world map: station, selected satellite (footprint, ground track), APRS stations. */
@Composable
fun MapDialog(engine: Engine, onClose: () -> Unit) {
    val st by engine.status.collectAsState()
    val detail by engine.detail.collectAsState()
    MapDialog(st, detail, onClose)
}

@Composable
fun MapDialog(st: Status, detail: SatDetail?, onClose: () -> Unit) {
    Dialog(onDismissRequest = onClose, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize().background(Sea)) {
            WorldMap(st, detail, Modifier.fillMaxSize())
            val pins = mapPins(st)
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    (detail?.let { d -> d.name + (d.sub?.let { "  %.1f° %.1f°  %.0f km".format(it.first, it.second, it.third) } ?: "") } ?: "Map") +
                        "   ${pins.size} stations",
                    color = Color(0xFFE8E3D5), fontSize = 13.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f),
                )
                IconButton(onClick = onClose) { Icon(Icons.Filled.Close, contentDescription = "Close", tint = Color(0xFFE8E3D5)) }
            }
            if (pins.isNotEmpty()) {
                val fmt = SimpleDateFormat("HH:mm:ss", Locale.US)
                Column(
                    Modifier.align(Alignment.BottomStart).padding(8.dp)
                        .background(Color(0xCC0A0F16), RoundedCornerShape(8.dp)).padding(8.dp),
                ) {
                    for (p in pins.sortedByDescending { it.time }.take(6)) {
                        Text(
                            "%s %-10s %6.0f km".format(fmt.format(Date((p.time * 1000).toLong())), p.label, distanceKm(st.lat, st.lon, p.lat, p.lon)),
                            color = PinCol, fontSize = 11.sp, fontFamily = FontFamily.Monospace,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Equirectangular world map. Pinch to zoom, drag to pan, double tap to centre on the satellite
 * (or the station). The world repeats east and west, so a pass over the date line stays whole.
 */
@Composable
fun WorldMap(st: Status, detail: SatDetail?, modifier: Modifier = Modifier) {
    val ctx = LocalContext.current
    val land = remember { Land.get(ctx) }
    val tm = rememberTextMeasurer()
    var zoom by remember { mutableFloatStateOf(2.5f) }
    var center by remember { mutableStateOf(Pair(st.lon, st.lat)) }
    Canvas(
        modifier
            .pointerInput(Unit) {
                detectTransformGestures { _, pan, z, _ ->
                    val k = zoom * size.width / 360.0
                    zoom = (zoom * z).coerceIn(1f, 30f)
                    val (lon, lat) = center
                    center = Pair(lon - pan.x / k, (lat + pan.y / k).coerceIn(-85.0, 85.0))
                }
            }
            .pointerInput(detail?.norad) {
                detectTapGestures(onDoubleTap = {
                    center = detail?.sub?.let { Pair(it.second, it.first) } ?: Pair(st.lon, st.lat)
                })
            },
    ) {
        val k = zoom * size.width / 360.0
        val (cLon, cLat) = center
        fun x(lon: Double) = ((lon - cLon) * k + size.width / 2).toFloat()
        fun y(lat: Double) = ((cLat - lat) * k + size.height / 2).toFloat()
        // the copy of a longitude nearest the centre
        fun near(lon: Double) = lon - 360.0 * floor((lon - cLon + 180.0) / 360.0)
        val copies = listOf(-360.0, 0.0, 360.0)

        // graticule
        for (g in -180 until 180 step 30) for (c in copies) {
            val gx = x(near(g.toDouble()) + c)
            if (gx in 0f..size.width) drawLine(Grid, Offset(gx, y(90.0).coerceAtLeast(0f)), Offset(gx, y(-90.0).coerceAtMost(size.height)), 1f)
        }
        for (g in -60..60 step 30) drawLine(Grid, Offset(0f, y(g.toDouble())), Offset(size.width, y(g.toDouble())), 1f)

        // land: every ring clipped to the screen first. A path much larger than the screen (zoomed
        // in) makes the renderer rasterise it whole, which froze the app (lab16)
        val base = near(0.0)
        val path = Path()
        val m = 4f
        val box = floatArrayOf(-m, -m, size.width + m, size.height + m)
        for (c in copies) {
            for (r in land) {
                val n = r.size / 2
                val px = FloatArray(n) { x(r[2 * it] + base + c) }
                val py = FloatArray(n) { y(r[2 * it + 1].toDouble()) }
                if (px.max() < box[0] || px.min() > box[2] || py.max() < box[1] || py.min() > box[3]) continue
                val poly = clipPolygon(px, py, box)
                if (poly.size < 6) continue
                path.moveTo(poly[0], poly[1])
                var j = 2
                while (j < poly.size) {
                    path.lineTo(poly[j], poly[j + 1])
                    j += 2
                }
                path.close()
            }
        }
        drawPath(path, LandFill)
        drawPath(path, LandEdge, style = Stroke(1f))

        // satellite: footprint, ground track, position
        detail?.let { d ->
            if (d.ground.size > 1) {
                val nowIdx = 30
                line(d.ground.take(nowIdx + 1), ::x, ::y, ::near, Color(0x66FFC83C), 2f)
                line(d.ground.drop(nowIdx), ::x, ::y, ::near, SatYellow, 2.5f)
            }
            d.sub?.let { (lat, lon, h) ->
                val lam = acos(R_EARTH / (R_EARTH + h))
                val ring = (0..72).map { dest(lat, lon, lam, it * 5.0) }
                line(ring, ::x, ::y, ::near, Color(0xAA4FB3FF), 1.5f)
                val p = Offset(x(near(lon)), y(lat))
                drawCircle(SatYellow, 7f, p)
                drawText(tm, d.name, p + Offset(10f, -8f), TextStyle(color = SatYellow, fontSize = 12.sp))
            }
        }

        // station
        val q = Offset(x(near(st.lon)), y(st.lat))
        drawCircle(Accent, 6f, q)
        drawCircle(Accent, 12f, q, style = Stroke(2f))

        // APRS stations
        val pins = mapPins(st)
        for (p in pins) {
            val o = Offset(x(near(p.lon)), y(p.lat))
            drawCircle(PinCol, 5f, o)
            if (zoom >= 4f || pins.size <= 12) {
                drawText(tm, p.label, o + Offset(7f, -6f), TextStyle(color = PinCol, fontSize = 10.sp))
            }
        }
    }
}

/** A polyline of (lat, lon) points, broken where it crosses the edge of a world copy. */
private fun DrawScope.line(
    pts: List<Pair<Double, Double>>,
    x: (Double) -> Float,
    y: (Double) -> Float,
    near: (Double) -> Double,
    color: Color,
    width: Float,
) {
    if (pts.size < 2) return
    // segment by segment, each clipped to the screen (no huge paths, see the land above)
    val w = size.width
    val h = size.height
    val shifts = listOf(-360.0, 0.0, 360.0).map { x(it) - x(0.0) }
    var prevLon = near(pts[0].second)
    var x0 = x(prevLon)
    var y0 = y(pts[0].first)
    for (k in 1 until pts.size) {
        // keep the line continuous in longitude; the copies 360° away cover the wrap
        var lon = pts[k].second
        while (lon - prevLon > 180) lon -= 360
        while (lon - prevLon < -180) lon += 360
        val x1 = x(lon)
        val y1 = y(pts[k].first)
        for (dx in shifts) {
            clipSegment(x0 + dx, y0, x1 + dx, y1, w, h)?.let { (a, b) -> drawLine(color, a, b, width) }
        }
        prevLon = lon
        x0 = x1
        y0 = y1
    }
}

/** Liang-Barsky: the part of a segment inside the screen, or null. */
private fun clipSegment(x0: Float, y0: Float, x1: Float, y1: Float, w: Float, h: Float): Pair<Offset, Offset>? {
    val dx = x1 - x0
    val dy = y1 - y0
    var t0 = 0f
    var t1 = 1f
    val p = floatArrayOf(-dx, dx, -dy, dy)
    val q = floatArrayOf(x0, w - x0, y0, h - y0)
    for (i in 0..3) {
        if (p[i] == 0f) {
            if (q[i] < 0) return null
        } else {
            val t = q[i] / p[i]
            if (p[i] < 0) { if (t > t1) return null; if (t > t0) t0 = t } else { if (t < t0) return null; if (t < t1) t1 = t }
        }
    }
    return Pair(Offset(x0 + t0 * dx, y0 + t0 * dy), Offset(x0 + t1 * dx, y0 + t1 * dy))
}

/** Sutherland-Hodgman: a polygon clipped to the box (x0, y0, x1, y1), as x, y pairs. */
private fun clipPolygon(px: FloatArray, py: FloatArray, box: FloatArray): FloatArray {
    var xs = px.toList()
    var ys = py.toList()
    for (edge in 0..3) {
        if (xs.isEmpty()) break
        val nx = ArrayList<Float>(xs.size + 4)
        val ny = ArrayList<Float>(xs.size + 4)
        fun inside(x: Float, y: Float) = when (edge) {
            0 -> x >= box[0]
            1 -> x <= box[2]
            2 -> y >= box[1]
            else -> y <= box[3]
        }
        fun cross(ax: Float, ay: Float, bx: Float, by: Float): Pair<Float, Float> {
            val t = when (edge) {
                0 -> (box[0] - ax) / (bx - ax)
                1 -> (box[2] - ax) / (bx - ax)
                2 -> (box[1] - ay) / (by - ay)
                else -> (box[3] - ay) / (by - ay)
            }
            return Pair(ax + t * (bx - ax), ay + t * (by - ay))
        }
        for (i in xs.indices) {
            val ax = xs[(i + xs.size - 1) % xs.size]
            val ay = ys[(i + ys.size - 1) % ys.size]
            val bx = xs[i]
            val by = ys[i]
            val ain = inside(ax, ay)
            val bin = inside(bx, by)
            if (bin) {
                if (!ain) cross(ax, ay, bx, by).let { nx.add(it.first); ny.add(it.second) }
                nx.add(bx); ny.add(by)
            } else if (ain) {
                cross(ax, ay, bx, by).let { nx.add(it.first); ny.add(it.second) }
            }
        }
        xs = nx
        ys = ny
    }
    return FloatArray(xs.size * 2) { if (it % 2 == 0) xs[it / 2] else ys[it / 2] }
}

/** The point at angular distance `lam` (radians) and bearing `brg` (degrees) from (lat, lon). */
private fun dest(lat: Double, lon: Double, lam: Double, brg: Double): Pair<Double, Double> {
    val r = PI / 180
    val p1 = lat * r
    val b = brg * r
    val p2 = asin(sin(p1) * cos(lam) + cos(p1) * sin(lam) * cos(b))
    val l2 = lon * r + atan2(sin(b) * sin(lam) * cos(p1), cos(lam) - sin(p1) * sin(p2))
    return Pair(p2 / r, l2 / r)
}
