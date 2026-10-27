package harmonyai.platform.account

import android.content.Context
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/** Synthetic device checks; separate namespace, never reads or clears account proof. */
internal object DeviceChecks {
    fun run(context: Context): JSONObject {
        val vault = RefreshVault(context, "acceptance")
        val result = JSONObject()
        vault.clear()
        check(vault.take() == null)
        result.put("empty_take", true)
        val proof = "synthetic-only-" + UUID.randomUUID().toString()
        vault.write(proof)
        check(vault.take() == proof && vault.take() == null)
        result.put("single_consume", true)
        vault.write(proof)
        val executor = Executors.newFixedThreadPool(2)
        val start = CountDownLatch(1)
        try {
            val tasks = (0..1).map { executor.submit<String?> { start.await(); RefreshVault(context, "acceptance").take() } }
            start.countDown()
            val values = tasks.map { it.get(10, TimeUnit.SECONDS) }
            check(values.count { it == proof } == 1 && values.count { it == null } == 1)
            result.put("concurrent_consume", true)
        } finally { executor.shutdownNow() }
        vault.write(proof)
        vault.invalidateCurrentKeyForCheck()
        var denied = false
        try { vault.take() } catch (_: Exception) { denied = true }
        check(denied)
        vault.clear()
        result.put("missing_key_fails_closed", true)
        result.put("restart_kill_backup_checks", "NOT_RUN")
        result.put("source_version", "harmonyai-native-account-v0.1")
        return result
    }
}
