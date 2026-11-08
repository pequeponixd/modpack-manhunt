package cl.cachusafio.skins;

import com.mojang.logging.LogUtils;
import net.fabricmc.loader.api.FabricLoader;
import org.slf4j.Logger;

import java.io.Reader;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Properties;

/** config/cachusafio_skins.properties (en Forge era cachusafio_skins-common.toml, con las mismas opciones). */
public final class SkinsConfig {
    private static final Logger LOG = LogUtils.getLogger();
    public static boolean pinEnabled = true;
    public static int pinTimeoutSeconds = 20;

    private SkinsConfig() {}

    public static void load() {
        Path file = FabricLoader.getInstance().getConfigDir().resolve("cachusafio_skins.properties");
        Properties p = new Properties();
        try {
            if (Files.isRegularFile(file)) {
                try (Reader r = Files.newBufferedReader(file, StandardCharsets.UTF_8)) { p.load(r); }
            }
            pinEnabled = Boolean.parseBoolean(p.getProperty("activado", "true").trim());
            pinTimeoutSeconds = Math.max(5, Math.min(120, Integer.parseInt(p.getProperty("segundosParaVerificar", "20").trim())));
        } catch (Exception e) {
            LOG.warn("{} tiene un valor inválido; se usan los valores por defecto", file, e);
            pinEnabled = true;
            pinTimeoutSeconds = 20;
        }
        p.setProperty("activado", Boolean.toString(pinEnabled));
        p.setProperty("segundosParaVerificar", Integer.toString(pinTimeoutSeconds));
        try {
            Files.createDirectories(file.getParent());
            try (Writer w = Files.newBufferedWriter(file, StandardCharsets.UTF_8)) {
                p.store(w, " activado: pedir el PIN del launcher para entrar (solo servidores dedicados). Si lo apagas, cualquiera puede entrar con cualquier nombre.\n"
                        + " segundosParaVerificar: segundos (5-120) que tiene un jugador para mandar su PIN antes de ser expulsado.");
            }
        } catch (Exception e) {
            LOG.warn("No se pudo escribir {}", file, e);
        }
    }
}
