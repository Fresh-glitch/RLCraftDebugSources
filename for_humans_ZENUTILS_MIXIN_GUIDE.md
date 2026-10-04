# ZenUtils Mixin Guide

A concise reference for writing mixins in ZenUtils for Minecraft 1.12.2 modded environments.

### AI Note

This was drafted by Claude, but using my knowledge and guidance, otherwise this would be riddled with errors.
I also personally checked and edited all of it.

## Basic Setup

Every mixin script requires the mixin loader:

```js
#loader mixin
```

For client-side only mixins, add:
```js
#sideonly client
```

Mixins happen inside (zen)classes that target existing java classes

```js
#mixin {targets: "com.example.TargetClass"}
zenClass TargetClassMixin {
    // Your mixin code here
}
```

## Annotation Syntax Variants

ZenUtils supports both multi-line and single-line annotation formats:

**Multi-line format:**
```js
#mixin Inject
#{
#   method: "targetMethod",
#   at: {value: "HEAD"},
#   cancellable: true
#}
function myInjector(ci as mixin.CallbackInfo) as void { }
```

**Single-line format:**
```js
#mixin Inject {method: "targetMethod", at: {value: "HEAD"}, cancellable: true}
function myInjector(ci as mixin.CallbackInfo) as void { }
```

## SRG Remapping Rules

You will sometimes get a "hits no injection point" in your CT logs. This is often due to remapping issues. ZenUtils uses `remap=false` by default.
So you will need to obfuscate minecraft methods and fields to their SRG names yourself.

```js
# Correct - vanilla method in @At uses SRG name
at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;func_70097_a(...)"}

# Wrong - will fail to find target
at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;attackEntityFrom(...)"}
```

The same is true for method targets in injectors.

Inside method bodies, you can but probably shouldn't use SRG names.
   ```js
   // works
   this0.setMaxStackSize(16);
   world.getBlockState(pos).getBlock();

    // Also works
   this0.func_77625_d(16); 
   world.func_180495_p(pos).func_177230_c();
   ```

Mod methods/fields don't have this issue and use their normal names everywhere.

Never use `remap=false`. It is automatically set for all the mixins and will intentionally crash.

**How to find SRG names:**

Use MCP mapping files (methods.csv and fields.csv). These can be found on the internet (you want stable39-1.12) or are created by ForgeGradle inside any modding project inside `build/extractMappings`.

## Generics Always Return Object

Java generics are erased at runtime. ZenUtils cannot infer generic types:

```js
// Operation.call() always returns Object - must cast to actual type
#mixin WrapOperation
#{
#   method: "getLootTable",
#   at: {value: "INVOKE", target: "Lnet/minecraft/world/World;getLootTableManager()Lnet/minecraft/world/storage/loot/LootTableManager;"}
#}
function wrapGetLootManager(world as World, original as mixin.Operation) as native.net.minecraft.world.storage.loot.LootTableManager {
    val manager = original.call(world); // Returns Object, not LootTableManager
    // Must cast from Object to the actual return type
    return manager as native.net.minecraft.world.storage.loot.LootTableManager;
}
```

Always explicitly cast when dealing with generic return types.

## Accessing Target Class Members

Use `this0` to access the target class instance:

```js
#mixin {targets: "net.minecraft.entity.player.EntityPlayer"}
zenClass PlayerMixin {
    function doSomething() as void {
        val health = this0.getHealth(); // this0 is already cast to EntityPlayer
        this0.ticksExisted; // Can access fields directly
    }
}
```

This is a shortcut for using `(MyTargetClass) (Object) this` in java mixins.

## Static Methods

When targeting static methods, you need to mark your mixin method as static too:

```js
#mixin Static
#mixin Inject {method: "staticMethod", at: {value: "INVOKE", target: "Lsome/possibly/nonStatic/InjectorTarget;method()V"}}
function myStaticInjector(ci as mixin.CallbackInfo) as void { }
```

## @At Injection Points

The `at` parameter specifies where in the target method to inject. Here are the most common available injection points:

### Basic Injection Points

**HEAD** - At the very start of the method, before any code executes:
```js
at: {value: "HEAD"}
```

**RETURN** - At return statements (can target specific returns with `ordinal`):
```js
at: {value: "RETURN"}
at: {value: "RETURN", ordinal: 0}  // First return only
```

**TAIL** - Before the final return (before method exits).
```js
at: {value: "TAIL"}
```

### Targeting Instructions

**INVOKE** - At method calls. Requires `target` to specify which method:
```js
at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;func_70097_a(...)Z"}
at: {value: "INVOKE", target: "Ljava/util/List;add(Ljava/lang/Object;)Z", ordinal: 0}
```

**FIELD** - At field access (get or put). Requires `target`:
```js
at: {value: "FIELD", target: "Lnet/minecraft/entity/Entity;field_70143_R:F"}  // fallDistance
at: {value: "FIELD", target: "Lnet/minecraft/world/World;field_72995_K:Z", opcode: 180}  // isRemote; opcode is optional, 180 = GETFIELD, 181 = PUTFIELD
```

**NEW** - At object allocation (the NEW bytecode, before constructor runs):
```js
at: {value: "NEW", target: "Lnet/minecraft/item/ItemStack;"}
// Can optionally specify constructor signature to validate
at: {value: "NEW", target: "(Lnet/minecraft/item/Item;)Lnet/minecraft/item/ItemStack;"}
```

**Note:** `NEW` targets object allocation. To target the constructor call itself, use `INVOKE` with `<init>`:
```js
at: {value: "INVOKE", target: "Lnet/minecraft/item/ItemStack;<init>(Lnet/minecraft/item/Item;)V"}
```

**CONSTANT** - Targets constant values in bytecode. Can be used with any injector:
```js
// In most injectors, use CONSTANT in @At:
at: {value: "CONSTANT", intValue: 60}
at: {value: "CONSTANT", stringValue: "example"}

// In @ModifyConstant annotation, use the constant parameter:
constant: {intValue: 60}
constant: {floatValue: 1.5}
constant: {stringValue: "example"}
constant: {classValue: "Lnet/minecraft/entity/Entity;"}
constant: {nullValue: true}
```

**STORE / LOAD** - Only for `@ModifyVariable`, targets local variable operations:
```js
at: {value: "STORE", ordinal: 0}  // When variable is written to
at: {value: "LOAD", ordinal: 1}   // When variable is read the second time
```

**MIXINEXTRAS:EXPRESSION** - For `@Expression`:
```js
at: {value: "MIXINEXTRAS:EXPRESSION"}
// Requires #mixin Definition and #mixin Expression annotations
```

Other less common injection points: `JUMP`, `INVOKE_ASSIGN`, `INVOKE_STRING`, `CTOR_HEAD`

### Common @At Parameters

**ordinal** - Which occurrence to target (0-indexed):
```js
at: {value: "INVOKE", target: "...", ordinal: 0}  // First occurrence
at: {value: "INVOKE", target: "...", ordinal: 1}  // Second occurrence
```

**shift** - Shift injection point relative to the target:
```js
at: {value: "INVOKE", target: "...", shift: "AFTER"}   // After the instruction
at: {value: "INVOKE", target: "...", shift: "BEFORE"}  // Most injections are already targeting before, but BEFORE makes them target one instruction earlier
at: {value: "INVOKE", target: "...", shift: "BY", by: 2}  // Shift by N instructions, discouraged
```

**opcode** - Target specific bytecode opcode:
```js
at: {value: "FIELD", target: "...", opcode: 180}  // 180 = GETFIELD
at: {value: "FIELD", target: "...", opcode: 181}  // 181 = PUTFIELD
```

### Slices

Using `slice` allows you to only target instructions between two named injection points `from` and `to`.
This shifts ordinals, so ordinal=0 is the first instance happening in the slice.
This is safer than using ordinals greater than 0, as counting can be brittle if other mixins inject code in the same target before your injection.

```js
method: "...",
at: {value: "...", target: "..."}, 
slice: {
    from: {value: "..." target: "..."}, 
    to: {value: "..." target: "..."}
}
```

### Target String Format

When using `target` parameter for methods/fields, use JVM descriptor format.
Vanilla members still need their SRG names here (see SRG Remapping Rules):

**Method targets:**
```
Lpackage/ClassName;methodName(ParameterTypes)ReturnType
```

**Examples:**
```js
"Lnet/minecraft/entity/Entity;func_70097_a(Lnet/minecraft/util/DamageSource;F)Z"  // attackEntityFrom
"Ljava/util/List;add(Ljava/lang/Object;)Z"
"Lnet/minecraft/item/ItemStack;func_77973_b()Lnet/minecraft/item/Item;"  // getItem
```

**Field targets:**
```
Lpackage/ClassName;fieldName:Type
```

**Examples:**
```js
"Lnet/minecraft/entity/Entity;field_70143_R:F"  // fallDistance
"Lnet/minecraft/world/World;field_72995_K:Z"  // isRemote
```

For more info refer to https://docs.fabricmc.net/develop/mixins/bytecode.

IntelliJ with the MinecraftDev plugin can directly give you target names with Rightclick -> Copy Special -> Mixin Target Reference.
Inspecting the bytecode also provides you with the descriptors.

## Injector Examples

### ModifyExpressionValue (Recommended)

Intercept and modify method call or field-get return values:

```js
#mixin ModifyExpressionValue
#{
#   method: "func_70601_bi",
#   at: {value: "INVOKE", target: "Lcom/example/SomeClass;isValid()Z"}
#}
function modifyCheck(original as bool) as bool { // original is what SomeClass::isValid() returned
    if(original) return original;
    return this0.world.provider.getDimension() == 1;
}
```

### WrapOperation (Recommended)

Wrap method calls to conditionally execute or modify behavior:

```js
#mixin WrapOperation
#{
#   method: "<init>",
#   at: {value: "INVOKE", target: "Lcom/alcatrazescapee/notreepunching/common/items/ItemSaw;setNoRepair()Lnet/minecraft/item/Item;"}
#}
function zenutils_makeRepairable(item as native.com.alcatrazescapee.notreepunching.common.items.ItemSaw, original as mixin.Operation) as Item {
    return this0; // skip setting item.setNoRepair() by not executing original.call(item)
}
```

### Inject

Inject your own code at specific points, leaving the original code as is.

```js
#mixin Inject
#{
#   method: "onUsingTick",
#   at: {value: "HEAD"},
#   cancellable: true // use WrapMethod instead of Inject at HEAD & cancel for compatibility
#}
function addCooldownAtStart(stack as ItemStack, world as World, player as EntityPlayer, ci as mixin.CallbackInfo) as void {
    if(world.isRemote)
        player.getCooldownTracker().setCooldown(this0, 200);
    ci.cancel(); // you can do that, but that doesn't mean you should
}
```

**Note:**
Inject with `cancel()` to early return the target method can cause incompatibility with other mixins wanting to do the same.
There is often better ways than cancelling.
Inject at HEAD with cancel should rather use WrapMethod.
Inject at TAIL or RETURN with cancel should rather use ModifyReturnValue.

Target methods with non-void return type require `mixin.CallbackInfoReturnable` instead of `mixin.CallbackInfo`.
These are canceled with `cir.setReturnValue(newReturnValue)` instead of `ci.cancel()`;

### ModifyVariable

Modify local variables at specified points.
These are not only the normal targets like HEAD, INVOKE, FIELD etc., but also the special injection points STORE or LOAD which only work with ModifyVariable:

```js
#mixin ModifyVariable
#{
#   method: "processEntity",
#   at: {value: "STORE", ordinal: 0},
#   ordinal: 0 // first local of type float
#}
function modifyDamage(damage as float) as float {
    // Intercept when damage variable is stored, after the first STORE operation
    return damage * 2.0; // Double the damage
}
```

Use `ordinal` in `@At` to select which STORE/LOAD operation, and `ordinal` in the annotation to select which local variable of the given type.
You can also use `index` for the exact local variable slot independently of its type, or `name` for the local variable name.
Note that method parameters are also local variables. `index` is the slot in the local variable table: in a static method index 0 is the first parameter, in a non-static method index 0 is `this` and the first parameter is index 1. `long` and `double` locals take two slots each.

### ModifyArg

Change arguments passed to method calls:

```js
#mixin ModifyArg
#{
#   method: "rollRandomValue",
#   at: {value: "INVOKE", target: "Ljava/util/Random;nextInt(I)I", ordinal: 0}
#}
function changeMaxRoll(origMaxRoll as int) as int {
    return 6; // change rand.nextInt(origMaxRoll) to rand.nextInt(6)
}
```

If the target call has multiple arguments of the same type, you can use `index: 0` to target the first etc.

### ModifyConstant

Replace hardcoded constants:

```js
#mixin ModifyConstant
#{
#   method: "calculateDamage",
#   constant: {intValue: 60}
#}
function changeConstant(original as int) as int {
    return 20; // Replace constant 60 with 20
}
```

Available constant types: intValue, longValue, floatValue, doubleValue, stringValue, classValue, nullValue.

### ModifyReturnValue

Modify the return value of the target method at targeted return points:

```js
#mixin ModifyReturnValue
#{
#   method: "shouldSpawn",
#   at: {value: "RETURN", ordinal: 0}
#}
function modifyReturn(original as bool) as bool {
    return original && someAdditionalCheck();
}
```

### WrapWithCondition

Conditionally prevent method calls:

```js
#mixin WrapWithCondition
#{
#   method: "onPlayerCraft",
#   at: {value: "INVOKE", target: "Lcursedflames/bountifulbaubles/baubleeffect/EnumBaubleModifier;generateModifier(Lnet/minecraft/item/ItemStack;)V"}
#}
function shouldGenerateModifier(stack as native.net.minecraft.item.ItemStack) as bool {
    // Only generate a modifier if the item doesn't already have one
    return !(stack.hasTagCompound() && stack.getTagCompound().hasKey("baubleModifier"));
}
```

This only works with method calls that return void and with field writes, but is a nice shortcut vs using WrapOperation and just not using the given Operation (or redirecting to no op, don't do that).

### WrapMethod

Wrap an entire method.
Like @Overwrite or @Inject at HEAD and cancel, but chainable and thus compatible:

```js
#mixin WrapMethod {method: "calculateDamage"}
function wrapDamageCalc(attacker as Entity, target as Entity, original as mixin.Operation) as float {
    // Can completely replace logic or call original
    if(target.isInvulnerable()) return 0.0;

    val originalDamage = original.call(attacker, target) as float; // invoke calculateDamage(attacker, target);
    return originalDamage * 1.5; // Modify result
}
```

Your handler receives the target method's parameters, followed by an `Operation`. Call `original.call(...)` with the same parameters.
If your handler doesn't call `original`, other mods' changes inside that method are silently skipped too, so it only chains while it calls it.

### ModifyReceiver

Modify the receiver (the object) of a method call or field access:

```js
#mixin ModifyReceiver
#{
#   method: "damageEntity", // this would need to be obfuscated to SRG
#   at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;attackEntityFrom(Lnet/minecraft/util/DamageSource;F)Z"} // this too
#}
function changeTarget(originalTarget as Entity, source as native.net.minecraft.util.DamageSource, amount as float) as Entity {
    // Redirect the attack to a different entity
    if(someCondition) return differentEntity; // will run differentEntity.attackEntityFrom(source, amount);
    return originalTarget;
}
```

Your handler receives the original receiver, followed by the method call's arguments. This can chain with other injectors.

### Redirect (Avoid)

Redirects method calls - incompatible with other mixins targeting the same injection point.
Use `WrapOperation` or `ModifyExpressionValue` or other compatible injectors instead.

```js
#mixin Static
#mixin Redirect
#{
#   method: "generateRecipes",
#   at: {value: "INVOKE", target: "Ljava/util/List;addAll(Ljava/util/Collection;)Z", ordinal: 2}
#}
function dontAddRecipes(recipes as native.java.util.List, toAdd as native.java.util.Collection) as bool {
    return false; // Prevent adding
}
```

### Overwrite (Avoid at all cost)

Overwrites method entirely - incompatible with other mixins into the same method.
Only use this if you want to crash with other mods targeting this method.

```js
#mixin Overwrite
function myTargetMethod() as void {
    // This method now is mine
}
```

### @Expression (MixinExtras - Advanced)

Allows targeting bytecode patterns using Java-like expression syntax. Requires `#mixin Definition` and `#mixin Expression` to define identifiers used in the expression.

Use `at: {value: "MIXINEXTRAS:EXPRESSION"}`

```js
#mixin Definition {id: "enchantment", local: {type: "Lnet/minecraft/enchantment/Enchantment;", name: "enchantment"}}
#mixin Expression {value: "enchantment == null"}
#mixin ModifyExpressionValue
#{
#   method: "deserialize",
#   at: {value: "MIXINEXTRAS:EXPRESSION"}
#}
function modifyNullCheck(original as bool) as bool {
    // Targets the "enchantment == null" comparison in bytecode
    return false; // Pretend its never null
}
```

**How it works:**
- `@Definition` declares identifiers (local variables, fields, methods, types)
- `@Expression` contains Java-like expression strings that reference those identifiers
- The expression is matched against the actual bytecode patterns
- Your handler modifies the value of that expression

**Definition types:**
- `local: {type: "Lcom/example/Class;", name: "x"}` - Define a local variable identifier. `type` is required and is a descriptor (`I` for an int); without it nothing matches
- `field: "Lcom/example/Class;fieldName:LType;"` - Define a field identifier
- `method: "Lcom/example/Class;methodName(...)V"` - Define a method identifier

This is an advanced feature - consult [MixinExtras Expressions Wiki](https://github.com/LlamaLad7/MixinExtras/wiki/Expressions) for detailed syntax.

## Appending Original Method Parameters

Injectors allow you to append the original target method's parameters to your signature:

```js
// Target method: processSpawn(EntityLivingBase entity, World world, int x, int y, int z)

#mixin ModifyExpressionValue
#{
#   method: "processSpawn",
#   at: {value: "INVOKE", target: "some method returning int"}
#}
function modifyField(original as int, entity as EntityLivingBase, world as World) as int {
    // Can access entity and world from original method signature
    if(world.provider.getDimension() == 1) return original * 2;
    return original;
}
```

Parameters must be in the same order as the target method. You can include as many or as few as needed.

## @Local Usage

Capture local variables from the target method:

```js
#mixin ModifyExpressionValue
#{
#   method: "processEntitySpawn",
#   at: {value: "FIELD", target: "Latomicstryker/infernalmobs/common/InfernalMobsCore;eliteRarity:I"}
#}
#mixin Local{argsOnly: true}
function captureLocal(original as int, entity as EntityLivingBase) as int {
    // 'entity' is a captured local variable (in this case a method parameter) from target method
    if(!(entity instanceof EntityParasiteBase)) return original;
    return (original / 1.5) as int;
}
```

**Local capture options:**
- `{argsOnly: true}` - only capture method parameters
- `{ordinal: 0}` - capture nth occurrence of a local type
- `{name: "myName"}` - capture local with given name (won't work for vanilla locals)
- `{index: 0}` - capture the local in that slot of the local variable table, independent of type (slot 0 is `this` in a non-static method)

Multiple locals can be captured. In that case specify parameter in #mixin Local to denote which of your mixin methods parameters each targets.
Counting starts with 0 for the first parameter of your method, no matter if that is already a captured local or a normal mixin method parameter.

```js
#mixin ModifyExpressionValue{method: "someMethod", at: {value: "TAIL"}}
#mixin Local{parameter: 1, name: "someLocal"}
#mixin Local{parameter: 2, name: "someOtherLocal"}
function captureLocal(original as int, someLocal as int, someOtherLocal as string) as int {
    // ...
}
```

In java Mixins you use LocalRef<OriginalType> to be able to modify locals, not just capture them. In ZenUtils this is done by making it an array and adding `ref: true`.

```js
#mixin ModifyExpressionValue{method: "someMethod", at: {value: "TAIL"}}
#mixin Local{name: "someLocal", ref: true}
function captureLocal(original as int, someLocal as int[]) as int {
    someLocal[0] = someLocal[0] + 5; // change the value of the local variable in the target method
}
```

## @Share Usage

Share allows you to create your own local variables in the target method that you can reuse in other injectors targeting the same method.
It works the same way as @Local, but you need to give it a name, and it needs to be a LocalRef = array.
ZenUtils before 1.28.7 puts `#mixin Share` on the handler method instead of its parameter, so on the pack's 1.27.5 it needs NischiTweaker 1.0.4 or later, which backports the fix ("Fix Share Annotation (ASM Toggle)", on by default).

```js
#mixin Inject {method: "loadConfig", at: {value: "HEAD"}}
#mixin Share{value: "shared"}
function setShared(ci as mixin.CallbackInfo, shared as int[]) as void {
    shared[0] = 42;
}

#mixin Inject {method: "loadConfig", at: {value: "TAIL"}}
#mixin Share{value: "shared"}
function readShared(ci as mixin.CallbackInfo, shared as int[]) as void {
    print(shared[0]); // 42, set by the HEAD injector
}
```

## @Cancellable Usage

Cancellable allows you to add a cancellable CallbackInfo/-Returnable in injectors that aren't @Inject.
It works the same way as @Local and @Share, by adding a method parameter of type mixin.CallbackInfo/-Returnable.

## @Shadow Usage

Access private fields/methods of the target class:

```js
#mixin {targets: "some.package.TargetClass"}
zenClass MyMixin {
    #mixin Shadow
    var privateField as int; // Shadow a private field

    #mixin Shadow
    function privateMethod(arg as int) as void { } // Shadow a private method

    function usePrivateMembers() as void {
        this0.privateField = 42;
        this0.privateMethod(this0.privateField);
    }
}
```

Shadowed members can be accessed via `this0` like normal members.

## Inner Classes

When targeting inner classes, use `$` in the target:

```js
#mixin {targets: "com.example.OuterClass$InnerClass"}
```

You cannot easily access the enclosing object (`OuterClass.this`) from within an inner member class mixin.
In normal mixins you'd do that with `this$0` (or $1, $2 etc for even more nested classes) but $ is not allowed in zenscript.
Workaround by using the aliases property of @Shadow like this:

```js
#mixin Shadow{aliases: "this$0"}
var outer as OuterClass;
```

## Adding methods and fields

**Adding fields:**
```js
#mixin {targets: "melonslise.locks.common.init.LocksItems"}
zenClass LocksItemsMixin {
    static DRAGONBONE_LOCK_PICK as Item; // Add static field

    #mixin Static
    #mixin Inject {method: "<clinit>", at: {value: "TAIL"}}
    function registerCustomItem(ci as mixin.CallbackInfo) as void {
        DRAGONBONE_LOCK_PICK = native.melonslise.locks.common.item.LockPickItem(0.97);
        // Field is now accessible from outside as native.melonslise.locks.common.init.LocksItems.DRAGONBONE_LOCK_PICK
    }
}
```

**Adding methods:**

In normal mixins you would add a duck interface to give the target class externally accessible methods.
In ZenUtils this is instead done by just adding methods without a duck interface and calling them from outside using native access.

Methods without injector annotations are added to the target class:

```js
#mixin {targets: "com.example.TargetClass"}
zenClass TargetClassMixin {
    // Helper method
    function myHelper() as int {
        return this0.someField * 3;
    }

    #mixin ModifyReturnValue {method: "getValue", at: {value: "RETURN"}}
    function modifyValue(original as int) as int {
        return original + myHelper(); // Can call helper from injector, but also from anywhere else as native.com.example.TargetClass.myHelper()
    }
}
```

Note that to make an added method static, you need to add `#mixin Static`.

## Inheritance

Mixin zenClasses can extend any of the target class's superclasses to gain access to the `super` keyword for calling parent methods:

```js
#mixin {targets: "some.mod.SomeItem"}
zenClass SomeItemMixin extends native.net.minecraft.item.Item {
    // can now use super.anyItemMethod()
}
```

## Configuration System

ZenUtils mixins can use configurable values by combining fields with ZenUtils configs:

**Step 1: Define config delegation fields in mixin classes**

```js
#mixin {targets: "noppes.vc.items.ItemMusket"}
zenClass ItemMusketMixin {
    static zenutils_cfg_val as int = 20; // Default value

    #mixin ModifyConstant {method: "onUsingTick", constant: {intValue: 60}}
    function changeLoadingTime(original as int) as int {
        return zenutils_cfg_val; // Use static field
    }
}
```

**Step 2: Register config options**

Create `_zenutilsconfigs.zs`:

```js
#loader preinit

import mods.zenutils.config.ConfigUtils;

ConfigUtils.named("mymodpack")
.withGui(
    ConfigUtils.createMeta("My Modpack")
        .setDescription("Config for my modpack tweaks")
        .setVersion("1.0.0")
        .addAuthor("YourName")
)
.category("weapons")
    .rangedInteger("musketLoadingTicks", 20, 0, 100)
        .sliding()
        .displayName("Musket Loading Ticks")
        .comment("How long musket takes to reload. Default 60t = 3s.")
        .add()
.add()
.register();
```

**Step 3: Sync config to mixin fields**

Create `zenutils_mixinconfigupdate.zs`:

```js
#loader preinit

import dynamic.zenutils.config.Mymodpack; // Generated from config name
import mods.zenutils.EventPriority;

function update() as void {
    native.noppes.vc.items.ItemMusket.zenutils_cfg_val = Mymodpack.weapons.musketLoadingTicks;
    // Repeat for all configurable mixins
}

update(); // Initial sync on script load

events.register(function(event as native.net.minecraftforge.fml.client.event.ConfigChangedEvent.OnConfigChangedEvent) {
    if(event.getModID() != "mymodpack") return;
    update();
}, EventPriority.normal(), false);
```

Players can now edit values via in-game config GUI, and changes will update your mixin behavior.

Note that you can ofc change the script file names, but you need to ensure that the config script runs before the update script by having it come before it alphabetically or by loader order (rn both in preinit).

### A note about compatibility

-- Argument by WaitingIdly --

The above notes about (in-)compatibility of certain injectors are how people should think about their injections in a java modding context.
Mods should try to be compatible not just with the current amount of released mods, but all potential future mods, to the extent of their capabilities.

You as a modpack author are in a slightly different position. Your mixins only have to work in your modpack.
So if your targeted code isn't already claimed by other mixins in your pack,
(and if you assume it will stay that way even if you add mods in the future,)
you can decide freely whether you want to worry about compatibility.

Using Overwrite, Redirect and Inject & cancel can be more straightforward than surgically creating a mixin that only changes the bit of code you actually want to change.

You can check if code is already claimed by using the jvm flag `-Dmixin.debug.export` and folder `.mixin.out`.
If the target class doesn't exist in the folder, no mixins target it yet.
Otherwise let your favorite decompiler show you the .class file as java code (IDEs do that automatically) and search for the target method, see if it got modified.

## Further Resources

- ZenUtils Wiki: https://github.com/friendlyhj/ZenUtils/wiki/Mixin
- Mixin JavaDocs: https://github.com/SpongePowered/Mixin/tree/master/src/main/java/org/spongepowered/asm/mixin/injection
- MixinExtras Documentation: https://github.com/LlamaLad7/MixinExtras/wiki
