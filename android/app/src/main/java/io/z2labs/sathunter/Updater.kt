package io.z2labs.sathunter

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL

/**
 * Self update from the GitHub releases of z2labs/SatHunter-SDR.
 *
 * Every CI build is signed with the same release key and carries a growing versionCode, so a
 * newer release installs over this one. Android lets an app download and open the installer,
 * but the user confirms the install (one tap); the first time Android also asks to allow
 * installs from SatHunterSDR.
 */
class Updater(private val ctx: Context) {
    data class Release(val tag: String, val name: String, val prerelease: Boolean, val apkUrl: String, val size: Long, val published: String)

    sealed class State {
        object Idle : State()
        object Checking : State()
        data class UpToDate(val latest: String) : State()
        data class Available(val rel: Release) : State()
        data class Downloading(val rel: Release, val done: Long) : State()
        data class Installing(val rel: Release) : State()
        data class Failed(val msg: String) : State()
    }

    private val _state = MutableStateFlow<State>(State.Idle)
    val state: StateFlow<State> = _state
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val prefs = ctx.getSharedPreferences("update", Context.MODE_PRIVATE)

    var includePrerelease: Boolean
        get() = prefs.getBoolean("prerelease", true)
        set(v) = prefs.edit().putBoolean("prerelease", v).apply()

    /** This build's tag, as the CI names releases (v + versionName). */
    private val current = "v" + BuildConfig.VERSION_NAME

    /** Newest release for this channel; a different tag that is newer than this build is offered. */
    fun check(prerelease: Boolean = includePrerelease, thenInstall: Boolean = false) {
        if (_state.value is State.Checking || _state.value is State.Downloading) return
        _state.value = State.Checking
        scope.launch {
            try {
                val c = URL("https://api.github.com/repos/$REPO/releases?per_page=20").openConnection() as HttpURLConnection
                c.setRequestProperty("Accept", "application/vnd.github+json")
                c.setRequestProperty("User-Agent", "SatHunterSDR/${BuildConfig.VERSION_NAME}")
                c.connectTimeout = 15_000
                c.readTimeout = 15_000
                if (c.responseCode != 200) throw Exception("GitHub: HTTP ${c.responseCode}")
                val a = JSONArray(c.inputStream.bufferedReader().readText())
                val rel = (0 until a.length()).map { a.getJSONObject(it) }
                    .filter { !it.optBoolean("draft") && (prerelease || !it.optBoolean("prerelease")) }
                    .mapNotNull { r ->
                        val assets = r.optJSONArray("assets") ?: return@mapNotNull null
                        val apk = (0 until assets.length()).map { assets.getJSONObject(it) }.firstOrNull { it.optString("name").endsWith(".apk") }
                            ?: return@mapNotNull null
                        Release(r.optString("tag_name"), r.optString("name"), r.optBoolean("prerelease"),
                            apk.optString("browser_download_url"), apk.optLong("size"), r.optString("published_at"))
                    }
                    .maxByOrNull { it.published }  // ISO 8601: sorts as text
                when {
                    rel == null -> _state.value = State.Failed("no release with an APK found")
                    rel.tag == current || rel.published.take(19) <= BuildConfig.BUILD_TIME.take(19) -> _state.value = State.UpToDate(rel.tag)
                    else -> {
                        _state.value = State.Available(rel)
                        if (thenInstall) install(rel)
                    }
                }
            } catch (e: Exception) {
                _state.value = State.Failed(e.message ?: e.toString())
            }
        }
    }

    /** Download the APK and hand it to the system installer (the user confirms). */
    fun install(rel: Release) {
        if (Build.VERSION.SDK_INT >= 26 && !ctx.packageManager.canRequestPackageInstalls()) {
            _state.value = State.Failed("Allow installs from SatHunterSDR, then press Update again")
            ctx.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${ctx.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        _state.value = State.Downloading(rel, 0)
        scope.launch {
            try {
                val pi = ctx.packageManager.packageInstaller
                val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
                // Ask for no confirmation where Android allows it (12+), unless that already failed
                // on this phone: MIUI aborts such sessions with "Permission denied" (Mi 10,
                // 2026-11-06), then the normal confirmed install is used
                if (Build.VERSION.SDK_INT >= 31 && !prefs.getBoolean("silent_failed", false)) {
                    params.setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
                }
                lastRel = rel
                val id = pi.createSession(params)
                pi.openSession(id).use { s ->
                    val c = URL(rel.apkUrl).openConnection() as HttpURLConnection
                    c.instanceFollowRedirects = true
                    c.setRequestProperty("User-Agent", "SatHunterSDR/${BuildConfig.VERSION_NAME}")
                    c.connectTimeout = 20_000
                    c.readTimeout = 60_000
                    if (c.responseCode != 200) throw Exception("download: HTTP ${c.responseCode}")
                    s.openWrite("SatHunterSDR.apk", 0, rel.size.takeIf { it > 0 } ?: -1).use { out ->
                        c.inputStream.use { inp ->
                            val buf = ByteArray(64 * 1024)
                            var done = 0L
                            var last = 0L
                            while (true) {
                                val n = inp.read(buf)
                                if (n < 0) break
                                out.write(buf, 0, n)
                                done += n
                                if (done - last > 512 * 1024) {
                                    _state.value = State.Downloading(rel, done)
                                    last = done
                                }
                            }
                        }
                        s.fsync(out)
                    }
                    val intent = Intent(ctx, UpdateReceiver::class.java).setAction(ACTION)
                    val flags = PendingIntent.FLAG_UPDATE_CURRENT or (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
                    s.commit(PendingIntent.getBroadcast(ctx, id, intent, flags).intentSender)
                }
                _state.value = State.Installing(rel)
            } catch (e: Exception) {
                _state.value = State.Failed(e.message ?: e.toString())
            }
        }
    }

    private var lastRel: Release? = null

    fun failed(status: Int, msg: String) {
        // A silent install refused by the system: remember it and install again the normal way
        val silent = Build.VERSION.SDK_INT >= 31 && !prefs.getBoolean("silent_failed", false)
        if (silent && status == PackageInstaller.STATUS_FAILURE_ABORTED) {
            prefs.edit().putBoolean("silent_failed", true).apply()
            lastRel?.let { install(it); return }
        }
        _state.value = State.Failed("install failed ($status): $msg")
    }

    /** False when this phone refused an update without confirmation (MIUI). */
    val silentWorks: Boolean get() = Build.VERSION.SDK_INT >= 31 && !prefs.getBoolean("silent_failed", false)

    companion object {
        const val REPO = "z2labs/SatHunter-SDR"
        const val ACTION = "io.z2labs.sathunter.UPDATE_STATUS"
        /** The running app's updater, for the receiver's error reports */
        var instance: Updater? = null
    }
}

/** Installer session results: opens the confirmation dialog, reports failures. */
class UpdateReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                @Suppress("DEPRECATION")
                val confirm = intent.getParcelableExtra<Intent>(Intent.EXTRA_INTENT) ?: return
                ctx.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            PackageInstaller.STATUS_SUCCESS -> {}
            else -> Updater.instance?.failed(status, intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "")
        }
    }
}
