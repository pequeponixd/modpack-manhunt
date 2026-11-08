package cl.cachusafio.skins.net;

import cl.cachusafio.skins.CachusafioSkins;
import cl.cachusafio.skins.server.PinAuth;
import cl.cachusafio.skins.server.ServerSkins;
import io.netty.buffer.Unpooled;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerPlayer;

import javax.annotation.Nullable;
import java.util.UUID;

/**
 * Un canal por paquete. Opcional en ambos lados: un servidor sin el mod deja entrar a clientes con él
 * (y al revés); en ese caso cada uno solo ve su propia skin.
 */
public final class SkinNetwork {
    /** Cliente → servidor: "esta es mi skin" (SkinData). */
    public static final ResourceLocation UPLOAD = new ResourceLocation(CachusafioSkins.MOD_ID, "upload");
    /** Servidor → cliente: skin de un jugador (UUID + SkinData opcional; sin datos = quitarla). */
    public static final ResourceLocation SYNC = new ResourceLocation(CachusafioSkins.MOD_ID, "sync");
    /** Cliente → servidor: clave derivada del PIN (64 hex) o "" si el juego no se abrió con el launcher. */
    public static final ResourceLocation PIN = new ResourceLocation(CachusafioSkins.MOD_ID, "pin");

    private SkinNetwork() {}

    public static void registerServer() {
        ServerPlayNetworking.registerGlobalReceiver(UPLOAD, (server, player, handler, buf, sender) -> {
            SkinData data = SkinData.read(buf);
            if (data != null) server.execute(() -> ServerSkins.receive(player, data));
        });
        ServerPlayNetworking.registerGlobalReceiver(PIN, (server, player, handler, buf, sender) -> {
            String token = buf.readUtf(64);
            server.execute(() -> PinAuth.receive(player, token));
        });
    }

    public static FriendlyByteBuf upload(SkinData data) {
        FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
        data.write(buf);
        return buf;
    }

    public static FriendlyByteBuf pin(String token) {
        FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
        buf.writeUtf(token, 64);
        return buf;
    }

    public static void sendSync(ServerPlayer to, UUID player, @Nullable SkinData data) {
        if (!ServerPlayNetworking.canSend(to, SYNC)) return;
        FriendlyByteBuf buf = new FriendlyByteBuf(Unpooled.buffer());
        buf.writeUUID(player);
        buf.writeBoolean(data != null);
        if (data != null) data.write(buf);
        ServerPlayNetworking.send(to, SYNC, buf);
    }
}
