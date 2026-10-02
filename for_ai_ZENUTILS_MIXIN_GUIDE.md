# AI_CONTEXT: ZenUtils mixins, MC 1.12.2 Forge, RLCraft (RLCraftParasited)
# FORMAT: dense rules for an LLM with no prior context. Human version: for_humans_ZENUTILS_MIXIN_GUIDE.md (read it for prose).
# PRIORITY: rules marked [HARD] break the mixin or crash if violated; [STYLE] = maintainer (Nischhelm) review standard.

## 0. WHAT / WHERE
- ZenUtils = CraftTweaker addon; `#loader mixin` scripts compile zenClasses into real SpongePowered Mixin classes at startup. Semantics = Mixin 0.8 + MixinExtras (WrapOperation, ModifyExpressionValue, WrapMethod, Local, Share, Expression all available).
- Default file targets (no other instruction): `../RLCraftParasited/overrides/scripts/zenutilsmixins.zs` (common), `zenutilsmixins_client.zs` (client only, has `#sideonly client`). Other existing mixin files: `greaterxptomemixins.zs`, `zenutilsmixins_rtg.zs`. Config: `_zenutilsconfigs.zs` + `zenutils_mixinconfigupdate.zs`.
- Mappings (stable_39): `mcpdeobfuscator/mappings/{methods,fields,params}.csv`, columns `searge,name,side,desc`. NO owner column.
- Readable source of any shipped jar: `python3 mcpdeobfuscator/deobfuscate_mods.py --mods-dir <mods> --only <jar substring>` -> `decompiled/<jar>/src/main/java` (MCP names). Needs Java 17+ first on PATH.
- `clone_repos.sh` = lookup table modid -> source repo URL. Repo != shipped build; target the SHIPPED jar.

## 1. WORKFLOW (do in order)
1. Find target: decompile shipped jar (sec 0). Read the whole target method AND the class's other methods with similar names before choosing.
2. Exact strings: `javap -p -c -classpath <jar> <fq.Class>` [HARD]. Mod jars ship SRG-named: every vanilla call/field/override inside mod bytecode already shows its SRG name and descriptor -> copy target strings from javap, never retype from decompiled source. javap also gives ordinals, lambda names (`lambda$method$N`), inner class names, static/non-static.
3. SRG lookup when not in any mod bytecode: grep csv by MCP name; multiple rows possible (`getHealth` -> `func_110143_aJ` EntityLivingBase AND `func_149332_c` other class); pick by desc/owner, then confirm by finding the SRG in some jar's javap. Overrides keep the parent's SRG name (`onLivingUpdate` = `func_70636_d` in every entity subclass).
4. Conflict check [HARD]: grep every jar (class files + `*.refmap.json` + mixin json) and every `scripts/*.zs` for the target class binary name `a/b/C` and dotted `a.b.C`. If another mixin injects into the same method: does it cancel (Inject HEAD `ci.cancel()` / `cir.setReturnValue` unconditionally)? Then yours may be applied but never run. Prefer chaining injectors so yours survives theirs.
5. Write mixin (sec 2-6). Smallest injector that does the job (sec 4 ranking).
6. Verify (sec 8). "No error in log" != works.

## 2. FILE / CLASS SKELETON
```
#loader mixin                       // [HARD] first line of every mixin script
#sideonly client                    // only for client-only targets (render/gui/input classes)

import native.net.minecraft.item.ItemStack;   // native Java types: `import native.<fqcn>;` then use simple name
import native.net.minecraft.entity.player.EntityPlayer;

// One plain comment line saying what/why (optional)
#mixin {targets: "com.mod.pkg.TargetClass"}          // or targets: ["a.B", "c.D"]
zenClass TargetClassMixin {                          // [STYLE] name = <TargetSimpleName>Mixin
    static zenutils_cfg_val as int = 20;            // [STYLE] statics first; config-fed statics named zenutils_cfg_*

    #mixin Shadow
    var someField as int;                            // private target field, use as bare `someField` or this0.someField

    #mixin <Injector>
    #{
    #   method: "targetMethod",
    #   at: {value: "...", target: "..."}
    #}
    function zenutils_doThing(<params>) as <ret> { ... }   // [STYLE] handler names zenutils_<camelCase>

    function zenutils_helper() as int { ... }       // no injector annotation = method ADDED to target class
}
```
- Annotation forms: multi-line `#mixin X` + `#{` ... `#}` lines, or single-line `#mixin X {k: v, ...}`. Keys use `:` [STYLE] (some pack lines use `ordinal = 1`; don't copy that).
- Modifier annotations stack ABOVE the injector line: `#mixin Static` then `#mixin Inject ...`. `#mixin Local{...}` / `#mixin Share` lines go AFTER the injector block, before `function`.
- Inner class target: `targets: "a.b.Outer$Inner"` / anonymous `"a.b.Outer$1"` [HARD: `$` here, `.` silently fails "target not found"]. In `native.` type refs use `.`: `native.java.util.Map.Entry`, `native.net.minecraftforge.event.RegistryEvent.Register`.
- ZenUtils refuses vanilla/early-loaded targets ("a non-mod class or already loaded"). Target a mod class or a Forge event handler instead; vanilla-only changes need a Java mod (FermiumMixins, sec 10).

## 3. NAMES / REMAP [HARD]
- ZenUtils sets remap=false on everything. NEVER write `remap` (crash).
- Therefore in `method:` and `at.target:` vanilla members MUST be SRG: `func_70097_a` (attackEntityFrom), `field_72995_K` (isRemote). MCP name there = "hits no injection point"/target not found.
- Mod members: always their source names (mods aren't obfuscated).
- Inside function bodies: MCP names work (`this0.world.isRemote`, `stack.getItem()`); SRG also works (`slot.field_75222_d`). [STYLE] prefer MCP in bodies; when an SRG name appears anywhere, add `// func_xxx = readableName`.
- `method:` special values: `"<init>"` constructor, `"<init>*"` all constructors, `"<clinit>"` static init, `"lambda$getSubBiomes$1"` (exact from javap), array `["func_77659_a", "addXP"]` for several.
- Descriptor syntax: method `Lowner/Class;name(ArgDescs)RetDesc`, field `Lowner/Class;name:Desc`. Desc: Z bool, B byte, C char, S short, I int, J long, F float, D double, V void, `Lpkg/Cls;` object, `[` array prefix. Owner may be omitted (`"func_184642_a(Lnet/minecraft/inventory/EntityEquipmentSlot;F)V"`) to match any owner.

## 4. INJECTOR CHOICE (top = prefer) [STYLE, compat]
| goal | injector |
|---|---|
| change value a call/field-get returns | ModifyExpressionValue |
| wrap one call / field get / field set, maybe skip or call twice | WrapOperation |
| skip a void call or field write conditionally | WrapWithCondition |
| change one argument of a call | ModifyArg (index: N if several same-type args) |
| change a literal | ModifyConstant |
| change method's return | ModifyReturnValue |
| change a local at STORE/LOAD | ModifyVariable |
| change call receiver | ModifyReceiver |
| replace/guard whole method | WrapMethod (NOT Inject HEAD+cancel) |
| run extra code, nothing to change | Inject (no cancel) |
| AVOID | Redirect (exclusive per call site), Overwrite (crash with others), Inject+cancel |
- Maintainer direction: Nischhelm replaced Redirect with WrapOperation in FermiumMixins `294857d` ("allow other mixins to modify..."); new code should chain.
- WrapMethod / WrapOperation chain only while handler calls `original.call(...)`. Not calling it silently skips other mods' changes inside. Skip only on the branch that must skip.
- Inject+cancel / Redirect / Overwrite acceptable ONLY in pack scripts when step 1.4 showed no other mixin on that method (modpack-only argument, human guide "A note about compatibility"). Default: don't.

## 5. HANDLER SIGNATURES (ZenScript). T = type at the point; P... = target method params (append in order from first, optional)
```
Inject:                 function f(P..., ci as mixin.CallbackInfo) as void            // all P or none
Inject non-void target: function f(P..., cir as mixin.CallbackInfoReturnable) as void  // cir.setReturnValue(x) needs cancellable: true
ModifyExpressionValue:  function f(original as T, P...) as T
WrapOperation (call):   function f(receiver as R, callArgs..., original as mixin.Operation) as Ret   // static call: no receiver
WrapOperation field get:function f(receiver as R, original as mixin.Operation) as FieldT
WrapWithCondition:      function f(receiver as R, callArgs...) as bool        // or (receiver, newValue) for field write
ModifyArg:              function f(arg as T) as T
ModifyConstant:         function f(original as T) as T      // constant: {intValue|floatValue|doubleValue|longValue|stringValue|classValue|nullValue: ...}
ModifyReturnValue:      function f(original as T, P...) as T   // at RETURN = every return; ordinal for one
ModifyVariable:         function f(value as T) as T         // at STORE|LOAD + ordinal/index/name selects the local
ModifyReceiver:         function f(receiver as R, callArgs...) as R
WrapMethod:             function f(P..., original as mixin.Operation) as Ret  // original.call(P...)
Redirect:               function f(receiver as R, callArgs...) as Ret
```
- `original.call(...)` returns Object [HARD]: cast `original.call(x) as bool` / `as Block`. Void: just call.
- Generic Java types are erased: native `List`/`Map` values come back Object -> cast elements (`it.next() as native.java.util.Map.Entry`).
- Static target method [HARD]: `#mixin Static` on the handler (and on added static methods). Non-static handler on static target fails.
- Handler cannot be `void` for value injectors; ModifyX must return the value.

## 6. SUGAR / MEMBERS
- `#mixin Local` (no args): the single local of the handler param's type. `{ordinal: N}` Nth local of that type. `{name: "x"}` by LVT name (works on mod code, NOT vanilla: no LVT names). `{index: N}` = LVT SLOT: non-static method slot 0 = `this`, params start at 1, long/double take 2 slots. `{argsOnly: true}` = target params only. Several: one line each with `parameter: K` = index of YOUR handler param it binds (counting from 0, all handler params).
- Writable local: `#mixin Local{name: "x", ref: true}` + param type `int[]`; write `x[0] = ...` (= LocalRef).
- `#mixin Share`: injector-to-injector local in same target method, array-typed like ref (syntax per human guide; verify on ZenUtils wiki before relying).
- `#mixin Cancellable`: adds `ci`/`cir` param to non-Inject injectors.
- `#mixin Shadow` on `var`/`function` = target's existing (private) member. Outer instance of inner class: `#mixin Shadow{aliases: "this$0"} var outer as Outer;`.
- `#mixin Unique` on ADDED fields/methods [STYLE]: prevents name clash with other mixins.
- Added method (no injector annotation) becomes a real member of target: callable from other scripts as `native.<TargetFqcn>.zenutils_x()` (static) or on instances.
- `zenClass X extends native.<SuperOfTarget>` (or imported simple name) -> `super.method()` available. [STYLE] added override = delegate to `super`, don't retype vanilla body; mark `// @Override`.
- Static field with init: `static zenutils_x as int = 3;`; set in `<clinit>` TAIL inject (`#mixin Static`) if computed.
- `this0` = target instance already cast to target type [HARD gotcha]: resolves ONLY real Java members of the target. Mixin-ADDED members via `this0.` fail ("no such member", returns null). Call added members by bare name; added statics also via `ThisMixinName.field`.

## 7. ZENSCRIPT BODY FACTS
- Construct without `new`: `ResourceLocation(a, b)`, `native.java.util.LinkedHashSet(c)`, `NBTTagCompound()`.
- Cast `x as T`; float literals `0.0F` or `(x as float)`; `isNull(x)` not `== null`; `instanceof` works with native types; class literal `Foo.class`.
- Arrays: `[T]` or `T[]`; literal `["a","b"] as string[]`; contains: `arr has "x"`; `for x in arr`; `while (...)`; ternary ok.
- `for x in` over native `List` works; over native `Set` fails ("No iterator with 1 variables") -> use `.iterator()` + while. Native `Set.toString()` not callable.
- Static access of a Java static: `native.pkg.Cls.FIELD`, or import + `Cls.FIELD` (`Item.REGISTRY`, `PotionTypes.field_185229_a`).
- [HARD gotcha] Assigning to `native.wrong.pkg.Cls.field` (class doesn't exist) fails SILENTLY at runtime: no error, field keeps default. Copy fqcn from javap/decompiled package line.
- Comments: `//` [STYLE]; avoid `#` comments (collide with directives).

## 8. VERIFY [HARD]
- crafttweaker.log per mixin: "Loaded mixin class" + "Applying mixin class" = took; "Skip loading mixin class ..., because the target ... is not found" = wrong target name ($ vs ., package, client class on server); script compile errors also there.
- latest.log: InvalidInjectionException / "hits no injection point" / "Critical injection failure". Many configs set no `defaultRequire`, so an injector matching 0 points can be SILENT -> prove behaviour.
- Prove behaviour: dedicated server for server logic (client-only classes absent there -> `#sideonly client` for those); probe script `#priority -2000` with `print(...)` of statics to prove config sync; in-game test for client paths.
- `-Dmixin.debug.export=true` -> `.mixin.out/` holds transformed classes: shows every mixin applied to a class (conflict check, sec 1.4).
- Applied != runs: another mod's HEAD cancel in same method stops yours. Measure the state your code changes.

## 9. CONFIGURABLE MIXIN (3 parts, all needed)
1. Mixin class: `static zenutils_cfg_name as <T> = <default>;` read in handler.
2. `_zenutilsconfigs.zs`: add option inside existing `ConfigUtils.named("parasited")` chain, e.g. `.category("srp")` ... `.rangedInteger("key", def, min, max).sliding().displayName("..").comment("..").add()` ... `.add()`. Builders used in pack: `booleanValue(k,def)`, `doubleValue(k,def)`, `rangedInteger(k,def,min,max)`, `rangedDouble(k,def,min,max)`, `lowerRangedInteger(k,def,min)`, `stringArrayMap`; modifiers `.sliding()`, `.requiresMcRestart()`. Generated class: `dynamic.zenutils.config.Parasited` -> `Parasited.<key>` (root) / `Parasited.<category>.<key>`.
3. `zenutils_mixinconfigupdate.zs` function `update()`: `native.<TargetFqcn>.zenutils_cfg_name = Parasited.<path>;` (runs at load + OnConfigChangedEvent for modid "parasited"). Neither script has a `#loader` line; `_` prefix makes the config script load first (alphabetical). Keep that order.
- Verify part 3 with a probe (sec 7 silent-fail gotcha).

## 10. JAVA MIXIN DELTA (FermiumMixins / mod code, not ZenUtils)
- `remap = false` REQUIRED on mod-member `@Shadow`, `@Inject/@WrapMethod/... method=` and `@At target` of mod members; vanilla members remap normally (refmap, MCP names in annotations). Bodies: MCP names (ForgeGradle reobf).
- MixinExtras imports: `com.llamalad7.mixinextras.injector.wrapmethod.WrapMethod`, `...injector.wrapoperation.{WrapOperation,Operation}`, `...injector.{ModifyExpressionValue,ModifyReturnValue}`, `...sugar.Local`. FermiumBooter ships MixinExtras with WrapMethod.
- FermiumMixins layout: `fermiummixins/mixin/<modid>/<Target>_<Feature>Mixin.java`; accessors `I<Target>Accessor` (vanilla ones in `<modid>/vanilla/`); handlers `fermiummixins_<modid><Target>_<method>`; toggle in `fermiummixins/config/<Mod>Config.java` with `@MixinConfig.MixinToggle(earlyMixin|lateMixin = "mixins.fermiummixins.<early|late>.<modid>.<feature>.json", defaultValue = false)` + `@MixinConfig.CompatHandling(modid=..., desired=true, reason=...)` + `@Config.RequiresMcRestart`; option name: copy the neighbouring options' pattern in that file (e.g. `"Fix Health Display (FirstAid)"`). JSON: `"mixins"` common, `"client"` client-only. Vanilla targets -> early json; mod targets -> late json. Repo stores LF (text=auto), working tree CRLF on Windows.
- `@Shadow private int x;` writable if not final (`@Mutable` + `@Final` for final).

## 11. STYLE (maintainer review = Nischhelm) [STYLE]
- Short: one plain comment line where non-obvious; NO block comments / essays ("ai yapping" gets cut). Reasoning goes in PR text.
- `if(` no space; braceless one-line ifs; `else` on own line ok; statics top, injectors before added methods.
- Library helpers over hand logic (`MathHelper.clamp` not two ifs). Delegate (`super.`) over restating vanilla.
- Fallback values must fail toward "nothing gained" (e.g. XP tome damage MAX = empty, not 0 = full).
- Commit messages: one lowercase line. Contributor credit only to the human; no AI name/trailer/footer in commits, PRs, comments.
- PR/fix direction: continue the author's latest change, never undo it (check `git log` of the file and his newest sibling mod's pattern).

## 12. MINIMAL VERIFIED EXAMPLES (all run in the pack)
```
// WrapOperation on a void call, conditional original (I&F Amphithere: post Forge tame event)
#mixin {targets: "com.github.alexthe666.iceandfire.entity.EntityAmphithere"}
zenClass EntityAmphithereMixin {
    #mixin WrapOperation
    #{
    #   method: "func_70636_d",
    #   at: {value: "INVOKE", target: "Lcom/github/alexthe666/iceandfire/entity/EntityAmphithere;func_193101_c(Lnet/minecraft/entity/player/EntityPlayer;)V"}
    #}
    function zenutils_postTameEvent(amphithere as native.com.github.alexthe666.iceandfire.entity.EntityAmphithere, player as EntityPlayer, original as mixin.Operation) as void {
        if(!native.net.minecraftforge.event.ForgeEventFactory.onAnimalTame(amphithere, player))
            original.call(amphithere, player);
    }
}

// ModifyExpressionValue + appended target param via Local argsOnly
#mixin {targets: "atomicstryker.infernalmobs.common.InfernalMobsCore"}
zenClass InfernalMobsCoreMixin {
    #mixin ModifyExpressionValue
    #{
    #   method: "processEntitySpawn",
    #   at: {value: "FIELD", target: "Latomicstryker/infernalmobs/common/InfernalMobsCore;eliteRarity:I"}
    #}
    #mixin Local{argsOnly: true}
    function zenutils_modifyInfernalChance(original as int, entity as EntityLivingBase) as int { ... }
}

// Static target + WrapWithCondition on a void call
#mixin {targets: "cursedflames.bountifulbaubles.baubleeffect.BaubleAttributeModifierHandler"}
zenClass BaubleAttributeModifierHandlerMixin {
    #mixin Static
    #mixin WrapWithCondition
    #{
    #   method: "onPlayerCraft",
    #   at: {value: "INVOKE", target: "Lcursedflames/bountifulbaubles/baubleeffect/EnumBaubleModifier;generateModifier(Lnet/minecraft/item/ItemStack;)V"}
    #}
    function zenutils_onlyGenerateModifierIfMissing(stack as ItemStack) as bool {
        return !(stack.hasTagCompound() && stack.getTagCompound().hasKey("baubleModifier"));
    }
}

// ModifyVariable at LOAD by name + two named Locals bound by parameter index; inner class target with $
#mixin {targets: "com.charles445.rltweaker.handler.QuarkHandler$QKAncientTomeAnvilUpdate"}
zenClass QuarkHandlerQKAncientTomeAnvilUpdateMixin {
    #mixin ModifyVariable
    #{
    #   method: "onUseItem",
    #   at: {value: "LOAD", ordinal: 0},
    #   name: "matched"
    #}
    #mixin Local{parameter: 1, name: "tomeEnchants"}
    #mixin Local{parameter: 2, name: "itemEnchants"}
    function zenutils_applyCurseBreak(matched as bool, tomeEnchants as native.java.util.Map, itemEnchants as native.java.util.Map) as bool { ... }
}
```

## 13. GOTCHA INDEX (each cost real time)
- `$` in targets, `.` in native refs.
- MCP name in at.target for vanilla -> no match. SRG from javap of mod jar.
- `this0.addedMethod()` -> null. Bare call.
- wrong `native.` path in assignment -> silent.
- ModifyConstant: `x > 0`/`x == 0` compile to zero-branch opcodes (no constant instruction) -> not found; `static final` constants are inlined at use sites -> target the literal where used, not the field.
- ordinal counts matching instructions in shipped bytecode of THAT method (0-based); prefer `slice: {from: {...}, to: {...}}` over ordinal > 0.
- Inject handler on non-void target needs CallbackInfoReturnable; cancelling needs `cancellable: true`.
- Client-only class (net.minecraft.client.*, render, gui) in a common script -> server crash/skip. Put in `zenutilsmixins_client.zs`.
- Applied mixin that never runs -> look for another mod cancelling same method first.
