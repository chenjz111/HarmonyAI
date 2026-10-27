package harmonyai.platform.account

import android.content.Context
import android.net.Uri
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.net.Proxy
import java.net.URI
import java.util.UUID
import okhttp3.OkHttpClient
import okhttp3.CookieJar
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.MediaType
import okhttp3.MultipartBody
import okio.BufferedSink
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.io.IOException

/** Test-only native transport; platform TLS validation is NEVER replaced. */
internal object NativeHttps {
    private const val MAX_BYTES = 25 * 1024 * 1024
    // Compile-only coordinates are explicit in config.json; DCloud supplies the
    // runtime classes. Native build and concrete APK linkage still need proof.
    // This client never uses JavaNetCookieJar/global CookieHandler or global clients.
    private val client = OkHttpClient.Builder().cookieJar(CookieJar.NO_COOKIES)
        .followRedirects(false).followSslRedirects(false).retryOnConnectionFailure(false)
        .proxy(Proxy.NO_PROXY).cache(null).connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS).writeTimeout(15, TimeUnit.SECONDS).build()
    private fun validateUrl(url: String, probe: Boolean, upload: Boolean) {
        require(!Regex("[\\u0000-\\u0020\\u007f\\\\]").containsMatchIn(url))
        val uri = URI(url)
        require(uri.scheme == "https" && uri.rawUserInfo == null && uri.rawFragment == null)
        require(uri.rawPath == uri.normalize().rawPath)
        // Gate the SAME canonical path that OkHttp will actually send. URI's
        // normalize() alone leaves encoded dot segments intact; HttpUrl folds
        // them, potentially moving a credentialed request outside /api/v3/.
        val canonical = Request.Builder().url(url).build().url()
        require(uri.rawPath == canonical.encodedPath())
        require(!canonical.encodedPath().contains('%'))
        if (probe) require(url in setOf("https://127.0.0.1:8443/health", "https://localhost:8443/health", "https://127.0.0.1:8444/health", "https://127.0.0.1:8443/__s7_platform_probe/redirect"))
        else {
            require(uri.host == "127.0.0.1" && uri.port == 8443)
            require(canonical.encodedPath().startsWith("/api/v3/") || canonical.encodedPath() == "/health" || (upload && canonical.encodedPath() == "/api/v2/documents"))
        }
    }
    private fun copyLimited(input: InputStream, output: java.io.OutputStream, limit: Int = MAX_BYTES) {
        val buffer = ByteArray(32768)
        var total = 0
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            total += read; check(total <= limit)
            output.write(buffer, 0, read)
        }
    }
    fun execute(context: Context, operation: String, args: JSONObject): JSONObject {
        val probe = operation == "network.probe"
        val upload = operation == "network.upload"
        val url = args.getString("url")
        validateUrl(url, probe, upload)
        if (probe) require(!args.has("header") && !args.has("body"))
        val builder = Request.Builder().url(url)
        val headers = args.optJSONObject("header") ?: JSONObject()
        val names = headers.keys()
        while (names.hasNext()) {
            val name = names.next()
            require(name.lowercase() in setOf("authorization", "content-type", "accept", "range", "idempotency-key", "if-range"))
            builder.header(name, headers.getString(name))
        }
        val method = if (upload) "POST" else if (probe) "GET" else args.optString("method", "GET")
        require(method in setOf("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"))
        var body: RequestBody? = null
        if (upload) {
            val name = args.optString("name", "file")
            require(Regex("[A-Za-z0-9_-]{1,64}").matches(name))
            val path = args.getString("filePath")
            val uri = Uri.parse(path)
            require(uri.scheme == null || uri.scheme in setOf("file", "content"))
            if (uri.scheme == null) require(path.startsWith("/"))
            val types = mapOf("jpg" to "image/jpeg", "jpeg" to "image/jpeg", "png" to "image/png", "pdf" to "application/pdf")
            val pathExt = (uri.lastPathSegment ?: path).substringAfterLast('.', "").lowercase()
            val mime = if (uri.scheme == "content") context.contentResolver.getType(uri) ?: types[pathExt] else types[pathExt]
            require(mime != null && mime in types.values)
            val extension = if (pathExt in types) pathExt else types.entries.first { it.value == mime }.key
            val fileBody = object : RequestBody() {
                override fun contentType(): MediaType? = MediaType.parse(mime)
                override fun writeTo(sink: BufferedSink) {
                    val input = if (uri.scheme == "content") context.contentResolver.openInputStream(uri) else File(uri.path ?: path).inputStream()
                    require(input != null)
                    input.use { copyLimited(it, sink.outputStream(), 10 * 1024 * 1024) }
                }
            }
            val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
            val fields = args.optJSONObject("formData") ?: JSONObject()
            val keys = fields.keys()
            while (keys.hasNext()) { val field=keys.next(); require(Regex("[A-Za-z0-9_-]{1,64}").matches(field)); multipart.addFormDataPart(field,fields.getString(field)) }
            body = multipart.addFormDataPart(name, "upload.$extension", fileBody).build()
        } else if (args.has("body") && !args.isNull("body")) {
            val bytes = args.getString("body").toByteArray(Charsets.UTF_8)
            require(bytes.size <= 2 * 1024 * 1024)
            body = RequestBody.create(MediaType.parse(headers.optString("Content-Type", "application/json")), bytes)
        } else if (method in setOf("POST", "PUT", "PATCH")) body = RequestBody.create(null, ByteArray(0))
        builder.method(method, body)
        var temporary: File? = null
        try {
            // A network interceptor gates every actual exchange, including 503 follow-up.
            val exchanges=AtomicInteger(0)
            val scopedClient=client.newBuilder().callTimeout(args.optLong("timeout",15000L).coerceIn(1000L,60000L),TimeUnit.MILLISECONDS)
                .addNetworkInterceptor { chain ->
                    if(exchanges.incrementAndGet()!=1)throw IOException("automatic exchange replay rejected")
                    chain.proceed(chain.request())
                }.build()
            val request=builder.build()
            validateUrl(request.url().toString(),probe,upload)
            scopedClient.newCall(request).execute().use { response ->
                val status = response.code()
                if (status in 300..399) throw RedirectRejected()
                val result = JSONObject().put("statusCode", status)
                val responseHeaders = JSONObject()
                for (name in listOf("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges", "Cache-Control")) response.header(name)?.let { responseHeaders.put(name,it) }
                result.put("header",responseHeaders)
                if (operation == "network.download" && status in 200..299) {
                    val file = File(context.cacheDir,"harmonyai-audio-"+UUID.randomUUID().toString()+".pending")
                    temporary=file
                    val responseBody=response.body() ?: throw IllegalStateException("audio unavailable")
                    responseBody.byteStream().use { input -> file.outputStream().use { output -> copyLimited(input,output); output.fd.sync() } }
                    val ready=File(file.parentFile,file.name.removeSuffix(".pending")+".mp3")
                    check(file.renameTo(ready))
                    result.put("tempFilePath",ready.absolutePath)
                    temporary=null
                } else {
                    val output=java.io.ByteArrayOutputStream()
                    response.body()?.byteStream()?.use { copyLimited(it,output,2*1024*1024) }
                    result.put("data",output.toString("UTF-8"))
                }
                return result
            }
        } finally { temporary?.delete() }
    }
    fun clearTemporaryAudio(context: Context): Int {
        val files=context.cacheDir.listFiles() ?: return 0
        return files.count { it.isFile && it.name.startsWith("harmonyai-audio-") && it.name.endsWith(".mp3") && it.delete() }
    }
    fun releaseTemporaryAudio(context: Context, path: String) {
        val file=File(path).canonicalFile
        require(file.parentFile==context.cacheDir.canonicalFile)
        require(Regex("harmonyai-audio-[0-9a-f-]{36}\\.mp3").matches(file.name))
        check(!file.exists() || (file.isFile && file.delete()))
    }
    class RedirectRejected : Exception()
}
