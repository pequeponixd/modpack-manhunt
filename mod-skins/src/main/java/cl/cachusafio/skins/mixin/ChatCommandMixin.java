package cl.cachusafio.skins.mixin;

import cl.cachusafio.skins.server.PinAuth;
import net.minecraft.network.protocol.game.ServerboundChatCommandPacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Fabric no tiene un evento para cancelar comandos: mientras se verifica el PIN, se ignoran. */
@Mixin(ServerGamePacketListenerImpl.class)
public abstract class ChatCommandMixin {
    @Shadow
    public ServerPlayer player;

    @Inject(method = "handleChatCommand", at = @At("HEAD"), cancellable = true)
    private void cachusafio$pending(ServerboundChatCommandPacket packet, CallbackInfo ci) {
        if (PinAuth.isPending(player)) ci.cancel();
    }
}
