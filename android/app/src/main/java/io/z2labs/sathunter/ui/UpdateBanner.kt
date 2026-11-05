package io.z2labs.sathunter.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.z2labs.sathunter.Updater

fun updateText(s: Updater.State): String = when (s) {
    Updater.State.Idle -> "Not checked yet"
    Updater.State.Checking -> "Checking GitHub..."
    is Updater.State.UpToDate -> "Up to date (latest: ${s.latest})"
    is Updater.State.Available -> "New version: ${s.rel.tag}"
    is Updater.State.Downloading -> "Downloading ${s.rel.tag}: ${s.done / 1_000_000} / ${s.rel.size / 1_000_000} MB"
    is Updater.State.Installing -> "Installing ${s.rel.tag}: confirm in the system dialog"
    is Updater.State.Failed -> "Update: ${s.msg}"
}

/** A slim bar on top while an update is on offer or in progress. */
@Composable
fun UpdateBanner(s: Updater.State, onUpdate: (Updater.Release) -> Unit, onDismiss: () -> Unit) {
    val show = s is Updater.State.Available || s is Updater.State.Downloading || s is Updater.State.Installing ||
        (s is Updater.State.Failed && !s.msg.startsWith("GitHub") && !s.msg.contains("Unable to resolve"))
    if (!show) return
    Row(Modifier.fillMaxWidth().background(Panel).padding(horizontal = 12.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(updateText(s), Modifier.weight(1f), color = Accent, fontSize = 13.sp)
        if (s is Updater.State.Available) TextButton(onClick = { onUpdate(s.rel) }) { Text("Update") }
        TextButton(onClick = onDismiss) { Text("Later") }
    }
}
