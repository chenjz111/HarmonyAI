package harmonyai.platform.account

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.io.File
import java.io.RandomAccessFile
import java.security.KeyStore
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Nonproduction candidate: one proof, encrypted by one AndroidKeyStore key.
 * The key is destroyed BEFORE a consumed plaintext can leave a committed txn.
 * A restored SQLite backup cannot decrypt a consumed proof. A crash between
 * key deletion and DB commit loses availability, never reauthorizes old proof.
 * Android crash/power-loss/backup evidence is still REQUIRED, not inferred.
 */
internal class RefreshVault(context: Context, private val namespace: String) {
    private val directory = File(context.noBackupFilesDir, "harmonyai-auth-v1")
    private val prefix = "harmonyai.auth.v1.$namespace."
    companion object { private val mutex = Any() }
    init { require(Build.VERSION.SDK_INT >= 23); require(namespace == "registered" || namespace == "acceptance") }
    private fun keys(): KeyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    private fun <T> locked(block: (SQLiteDatabase, KeyStore) -> T): T = synchronized(mutex) {
        check(directory.isDirectory || directory.mkdirs())
        RandomAccessFile(File(directory, "$namespace.lock"), "rw").use { lockFile ->
            lockFile.channel.lock().use {
                SQLiteDatabase.openOrCreateDatabase(File(directory, "$namespace.sqlite"), null).use { db ->
                    db.execSQL("PRAGMA journal_mode=DELETE")
                    db.execSQL("PRAGMA synchronous=EXTRA")
                    db.execSQL("PRAGMA secure_delete=ON")
                    db.execSQL("CREATE TABLE IF NOT EXISTS proof (slot INTEGER PRIMARY KEY CHECK(slot=1), alias TEXT NOT NULL, iv TEXT NOT NULL, ciphertext TEXT NOT NULL)")
                    db.beginTransaction()
                    try {
                        val result = block(db, keys())
                        db.setTransactionSuccessful()
                        // Kotlin finally ends (and commits) the FULL/EXTRA txn
                        // before the result is returned across the native bridge.
                        result
                    } finally { db.endTransaction() }
                }
            }
        }
    }
    private data class Row(val alias: String, val iv: String, val ciphertext: String)
    private fun row(db: SQLiteDatabase): Row? = db.rawQuery("SELECT alias,iv,ciphertext FROM proof WHERE slot=1", null).use {
        if (!it.moveToFirst()) null else Row(it.getString(0), it.getString(1), it.getString(2)).also { value -> check(value.alias.startsWith(prefix)) }
    }
    private fun destroy(keyStore: KeyStore, alias: String) {
        require(alias.startsWith(prefix))
        if (keyStore.containsAlias(alias)) keyStore.deleteEntry(alias)
        check(!keyStore.containsAlias(alias))
    }
    fun write(proof: String) = locked { db, keyStore ->
        require(proof.isNotEmpty() && proof.toByteArray(Charsets.UTF_8).size <= 8192)
        val alias = prefix + UUID.randomUUID().toString()
        try {
            val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            generator.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setKeySize(256).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true).build())
            val key = generator.generateKey()
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key)
            cipher.updateAAD(prefix.toByteArray(Charsets.UTF_8))
            val encoded = Base64.encodeToString(cipher.doFinal(proof.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
            val iv = Base64.encodeToString(cipher.iv, Base64.NO_WRAP)
            // Invalidate old ciphertext BEFORE replacing it, including rollback.
            row(db)?.let { destroy(keyStore, it.alias) }
            db.execSQL("INSERT OR REPLACE INTO proof(slot,alias,iv,ciphertext) VALUES(1,?,?,?)", arrayOf(alias, iv, encoded))
        } catch (error: Exception) {
            destroy(keyStore, alias)
            throw error
        }
    }
    fun take(): String? = locked { db, keyStore ->
        val record = row(db)
        if (record == null) null else {
            val key = keyStore.getKey(record.alias, null) as? SecretKey ?: throw IllegalStateException("secure key unavailable")
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key, GCMParameterSpec(128, Base64.decode(record.iv, Base64.NO_WRAP)))
            cipher.updateAAD(prefix.toByteArray(Charsets.UTF_8))
            val plaintext = cipher.doFinal(Base64.decode(record.ciphertext, Base64.NO_WRAP)).toString(Charsets.UTF_8)
            destroy(keyStore, record.alias)
            db.execSQL("DELETE FROM proof WHERE slot=1")
            plaintext
        }
    }
    fun clear() = locked { db, keyStore ->
        val aliases = keyStore.aliases().toList().filter { it.startsWith(prefix) }
        aliases.forEach { destroy(keyStore, it) }
        db.execSQL("DELETE FROM proof WHERE slot=1")
    }
    /** Acceptance namespace only; never expose arbitrary key deletion. */
    fun invalidateCurrentKeyForCheck() = locked { db, keyStore ->
        check(namespace == "acceptance")
        row(db)?.let { destroy(keyStore, it.alias) }
    }
}
