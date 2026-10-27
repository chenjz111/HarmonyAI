package harmonyai.platform.account

import android.content.Context
import android.os.Handler
import android.os.Looper
import org.json.JSONObject
import java.util.concurrent.Executors
import javax.net.ssl.SSLException

/** No automatic bootstrap or accepted/verified claims. Compile + device evidence required. */
object AccountNative {
    private val vaultWorker = Executors.newSingleThreadExecutor()
    private val networkWorker = Executors.newFixedThreadPool(2)
    @JvmStatic fun invoke(context: Context, operation: String, input: String, callback: (String) -> Unit) {
        val worker=if(operation.startsWith("vault."))vaultWorker else networkWorker
        worker.execute {
            val result = try {
                val args = JSONObject(input)
                val value: Any = when (operation) {
                    "vault.write" -> { RefreshVault(context, "registered").write(args.getString("proof")); JSONObject() }
                    "vault.take" -> JSONObject().put("proof", RefreshVault(context, "registered").take() ?: JSONObject.NULL)
                    "vault.clear" -> { RefreshVault(context, "registered").clear(); JSONObject() }
                    "vault.syntheticChecks" -> synchronized(DeviceChecks) { DeviceChecks.run(context) }
                    "audio.clearTemporary" -> JSONObject().put("removed",NativeHttps.clearTemporaryAudio(context))
                    "audio.releaseTemporary" -> { NativeHttps.releaseTemporaryAudio(context,args.getString("filePath")); JSONObject() }
                    "network.request", "network.upload", "network.download", "network.probe" -> NativeHttps.execute(context, operation, args)
                    else -> throw IllegalArgumentException("unsupported operation")
                }
                JSONObject().put("ok", true).put("data", value)
            } catch (_: NativeHttps.RedirectRejected) {
                JSONObject().put("ok", false).put("code", "NETWORK_REDIRECT_REJECTED")
            } catch (_: SSLException) {
                JSONObject().put("ok", false).put("code", "TLS_VALIDATION_FAILED")
            } catch (_: Exception) {
                // No password/proof, request body, URL query or platform exception logs.
                JSONObject().put("ok", false).put("code", "NATIVE_OPERATION_UNAVAILABLE")
            }
            Handler(Looper.getMainLooper()).post { callback(result.toString()) }
        }
    }
}
