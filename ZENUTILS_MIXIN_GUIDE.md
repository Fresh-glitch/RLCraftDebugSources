# ZenUtils Mixin Guide

A concise reference for writing mixins in ZenUtils for Minecraft 1.12.2 modded environments.

## Basic Setup

Every mixin script requires the mixin loader:

```js
#loader mixin

#mixin {targets: "com.example.TargetClass"}
zenClass MyMixin {
    // Your mixin code here
}
```

For client-side only mixins, add:
```js
#sideonly client
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

## CRITICAL: SRG Remapping Rules

**THIS IS EXTREMELY IMPORTANT:**

1. **At targets MUST use SRG names** when targeting vanilla methods/fields:
   ```js
   # CORRECT - vanilla method in @At uses SRG name
   at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;func_70097_a(...)"}

   # WRONG - will fail to find target
   at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;attackEntityFrom(...)"}
   ```

The same is true for method targets in injectors.

2. **Inside method bodies, you CAN but shouldn't use MCP names**
   ```js
   this0.setMaxStackSize(16); // MCP name works
   world.getBlockState(pos).getBlock(); // MCP names work

   // You could also use SRG names but its discouraged
   this0.func_77625_d(16); // Also works
   world.func_180495_p(pos).func_177230_c(); // Also works
   ```

3. **Mod methods/fields obv don't have this issue** and use their normal names everywhere

4. **NEVER use `remap=false`** - it will always crash in ZenUtils

**How to find SRG names:**

Use MCP mapping files (methods.csv, fields.csv in mcpdeobfuscator/mappings/)

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

## Static Methods

When targeting static methods, mark your mixin method as static:

```js
#mixin Static
#mixin Inject {method: "staticMethod", at: {value: "HEAD"}}
function myStaticInjector(ci as mixin.CallbackInfo) as void { }
```

**Important:** If the target method is static, your mixin method MUST be static too.

## @At Injection Points

The `at` parameter specifies where in the target method to inject. Here are the available injection points:

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
at: {value: "FIELD", target: "Lnet/minecraft/entity/Entity;health:F"}
at: {value: "FIELD", target: "Lnet/minecraft/world/World;isRemote:Z", opcode: 180}  // 180 = GETFIELD, 181 = PUTFIELD
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
The difference: `NEW` happens when memory is allocated, `<init>` happens when the object is initialized.

**CONSTANT** - Targets constant values in bytecode. Can be used with any injector, not just `@ModifyConstant`:
```js
// In @ModifyConstant annotation, use the constant parameter:
constant: {intValue: 60}
constant: {floatValue: 1.5}
constant: {stringValue: "example"}
constant: {classValue: "Lnet/minecraft/entity/Entity;"}
constant: {nullValue: true}

// In other injectors, use CONSTANT in @At:
at: {value: "CONSTANT", intValue: 60}
at: {value: "CONSTANT", stringValue: "example"}
```

**STORE / LOAD** - Only for `@ModifyVariable`, targets local variable operations:
```js
at: {value: "STORE", ordinal: 0}  // When variable is written
at: {value: "LOAD", ordinal: 1}   // When variable is read the second time
```

**MIXINEXTRAS:EXPRESSION** - For `@Expression`:
```js
at: {value: "MIXINEXTRAS:EXPRESSION"}
// Requires @Definition and @Expression annotations
```

### Common @At Parameters

**ordinal** - Which occurrence to target (0-indexed):
```js
at: {value: "INVOKE", target: "...", ordinal: 0}  // First occurrence
at: {value: "INVOKE", target: "...", ordinal: 1}  // Second occurrence
```

**shift** - Shift injection point relative to the target:
```js
at: {value: "INVOKE", target: "...", shift: "AFTER"}   // After the instruction
at: {value: "INVOKE", target: "...", shift: "BEFORE"}  // Before (default)
at: {value: "INVOKE", target: "...", shift: "BY", by: 2}  // Shift by N instructions, discouraged
```

**opcode** - Target specific bytecode opcode:
```js
at: {value: "FIELD", target: "...", opcode: 180}  // 180 = GETFIELD
at: {value: "FIELD", target: "...", opcode: 181}  // 181 = PUTFIELD
```

### Target String Format

When using `target` parameter for methods/fields, use JVM descriptor format:

**Method targets:**
```
Lpackage/ClassName;methodName(ParameterTypes)ReturnType
```

**Examples:**
```js
"Lnet/minecraft/entity/Entity;attackEntityFrom(Lnet/minecraft/util/DamageSource;F)Z"
"Ljava/util/List;add(Ljava/lang/Object;)Z"
"Lnet/minecraft/item/ItemStack;getItem()Lnet/minecraft/item/Item;"
```

**Field targets:**
```
Lpackage/ClassName;fieldName:Type
```

**Examples:**
```js
"Lnet/minecraft/entity/Entity;health:F"
"Lnet/minecraft/world/World;isRemote:Z"
```

**Remember:** Vanilla classes must use SRG names in targets (see SRG Remapping Rules section).

## Injector Examples

### ModifyExpressionValue (Recommended)

Intercept and modify method call return values:

```js
#mixin ModifyExpressionValue
#{
#   method: "func_70601_bi",
#   at: {value: "INVOKE", target: "Lcom/example/SomeClass;isValid()Z"}
#}
function modifyCheck(original as bool) as bool {
    if(original) return original;
    return this0.world.provider.getDimension() == 1;
}
```

### ModifyReceiver (MixinExtras)

Modify the receiver (the object) of a method call or field access:

```js
#mixin ModifyReceiver
#{
#   method: "damageEntity",
#   at: {value: "INVOKE", target: "Lnet/minecraft/entity/Entity;attackEntityFrom(...)Z"}
#}
function changeTarget(originalTarget as Entity, damageSource as native.net.minecraft.util.DamageSource, amount as float) as Entity {
    // Redirect the attack to a different entity
    if(someCondition) return differentEntity;
    return originalTarget; // Or keep original target
}
```

**Important:** Your handler receives the original receiver, followed by the method call's arguments. This chains with other injectors, unlike `@Redirect`.

### ModifyArg

Change arguments passed to method calls:

```js
#mixin ModifyArg
#{
#   method: "rollRandomValue",
#   at: {value: "INVOKE", target: "Ljava/util/Random;nextInt(I)I", ordinal: 0}
#}
function changeMaxRoll(origMaxRoll as int) as int {
    return 6; // Change from 10 to 6
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

### ModifyVariable

Modify local variables at specified points.
These are not only the normal targets like HEAD, INVOKE, FIELD etc., but also STORE or LOAD:

```js
#mixin ModifyVariable
#{
#   method: "processEntity",
#   at: {value: "STORE", ordinal: 0},
#   ordinal: 0
#}
function modifyDamage(damage as float) as float {
    // Intercept when damage variable is stored, after the first STORE operation
    return damage * 2.0; // Double the damage
}
```

**Important:** Use `ordinal` in `@At` to select which STORE/LOAD operation, and `ordinal` in the annotation to select which local variable of the given type. 
You can also use `index` for the exact local variable slot, or `name` for the local variable name.

### ModifyReturnValue

Modify the return value at targeted return points:

```js
#mixin ModifyReturnValue
#{
#   method: "shouldSpawn",
#   at: {value: "RETURN"}
#}
function modifyReturn(original as bool) as bool {
    return original && someAdditionalCheck();
}
```

### WrapOperation (Recommended)

Wrap method calls to conditionally execute or modify behavior:

```js
#mixin WrapOperation
#{
#   method: "processItems",
#   at: {value: "INVOKE", target: "Lnet/minecraft/item/Item;func_150895_a(...)V"}
#}
function wrapItemProcessing(item as Item, tab as native.net.minecraft.creativetab.CreativeTabs,
                           items as native.net.minecraft.util.NonNullList, original as mixin.Operation) as void {
    if(item instanceof native.some.mod.BadItem) return; // Skip bad items
    original.call(item, tab, items); // Call original for others
}
```

### WrapWithCondition (Recommended)

Conditionally prevent method calls:

```js
#mixin WrapWithCondition
#{
#   method: "register",
#   at: {value: "INVOKE", target: "Ljava/util/List;add(Ljava/lang/Object;)Z"}
#}
function shouldAddToList(list as native.java.util.List, element as native.java.lang.Object) as bool {
    return element != null && isValid(element); // Only add if valid
}
```

### WrapMethod

Wrap an entire method.
Like @Overwrite or @Inject at HEAD and cancel, but chainable:

```js
#mixin WrapMethod {method: "calculateDamage"}
function wrapDamageCalc(attacker as Entity, target as Entity, original as mixin.Operation) as float {
    // Can completely replace logic or call original
    if(target.isInvulnerable()) return 0.0;

    val originalDamage = original.call(attacker, target) as float;
    return originalDamage * 1.5; // Modify result
}
```

**Important:** Your handler receives the target method's parameters, followed by an `Operation`. Call `original.call(...)` with the same parameters.

### Inject

Inject code at specific points.

```js
#mixin Inject
#{
#   method: "onUsingTick",
#   at: {value: "HEAD"},
#   cancellable: true
#}
function addCooldownAtStart(stack as ItemStack, world as World, player as EntityPlayer,
                           ci as mixin.CallbackInfo) as void {
    if(world.isRemote)
        player.getCooldownTracker().setCooldown(this0, 200);
    ci.cancel(); //you can do that, but that doesn't mean you should
}
```

**Note:**
Inject with `cancel()` is poor style - causes incompatibility.
If you feel the need to cancel, rather **use MixinExtras injectors instead**.

Target methods with non-void return type require `mixin.CallbackInfoReturnable` instead of `mixin.CallbackInfo`. 
These are canceled with `cir.setReturnValue(newReturnValue)`;

### Redirect (Avoid)

Redirects method calls. **Poor style** - incompatible with other mixins. Use `WrapOperation` or `ModifyExpressionValue` instead.

```js
#mixin Static
#mixin Redirect
#{
#   method: "generateRecipes",
#   at: {value: "INVOKE", ordinal: 2, target: "Ljava/util/List;addAll(Ljava/util/Collection;)Z"}
#}
function dontAddRecipes(recipes as [SomeRecipe], toAdd as Collection) as bool {
    return false; // Prevent adding
}
```

### @Expression (MixinExtras - Advanced)

Allows targeting complex bytecode patterns using Java-like expression syntax. Requires `@Definition` to define identifiers used in the expression.

**Important:** Use `at: {"MIXINEXTRAS:EXPRESSION"}`

```js
#mixin Definition {id: "enchantment", local: {type: "net.minecraft.enchantment.Enchantment"}}
#mixin Expression {value: "enchantment == null"}
#mixin ModifyExpressionValue
#{
#   method: "deserialize",
#   at: {value: "MIXINEXTRAS:EXPRESSION"}
#}
#mixin Local{ordinal: 0}
function modifyNullCheck(original as bool, s as native.java.lang.String) as bool {
    // Targets the "enchantment == null" comparison in bytecode
    return false; // Change behavior
}
```

**How it works:**
- `@Definition` declares identifiers (local variables, fields, methods, types)
- `@Expression` contains Java-like expression strings that reference those identifiers
- The expression is matched against the actual bytecode patterns
- Your handler modifies the value of that expression

**Definition types:**
- `local: {type: "ClassName"}` - Define a local variable identifier
- `field: "Lcom/example/Class;fieldName:LType;"` - Define a field identifier
- `method: "Lcom/example/Class;methodName(...)V"` - Define a method identifier
- `type: "com.example.ClassName"` - Define a type identifier (for instanceof, new, etc.)

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
    // You can append all or just some parameters, in order
    if(entity.world.provider.getDimension() == 1) return original * 2;
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
    // 'entity' is captured from local variable in target method
    if(!(entity instanceof EntityParasiteBase)) return original;
    return (original / 1.5) as int;
}
```

**Local capture options:**
- `{argsOnly: true}` - only capture method parameters
- `{ordinal: 0}` - capture nth occurrence of a local type
- Multiple locals can be captured in order

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

## Why Avoid Overwrite, Redirect, and Inject+Cancel?

**Bad style - causes mod incompatibilities:**

- **Overwrite**: Completely replaces method - other mods can't inject
- **Redirect**: Hard redirects calls - conflicts with other redirects
- **Inject + cancel**: Prevents other mods from running their code

**Better alternatives:**
- Use **MixinExtras injectors** (`WrapOperation`, `WrapWithCondition`, `ModifyExpressionValue`, `WrapMethod`)
- These are more surgical and allow multiple mods to coexist
- Only use `Inject` without canceling for additive behavior

## Inner Classes

When targeting inner classes, use `.` instead of `$` in the target:

```js
# CORRECT
#mixin {targets: "com.example.OuterClass.InnerClass"}

# WRONG - will fail
#mixin {targets: "com.example.OuterClass$InnerClass"}
```

**Limitation:** You cannot access the enclosing object (`OuterClass.this`) from within an inner class mixin. In normal mixins you'd do that with `this$0`.

## Limitations

**What you CANNOT do:**
- Add duck interfaces for external APIs (ZenUtils limitation)
- Access enclosing object in inner class targets

**Adding fields:**
```js
#mixin {targets: "melonslise.locks.common.init.LocksItems"}
zenClass LocksItemsMixin {
    // Helper field WITH @Unique (RECOMMENDED to avoid conflicts)
    #mixin Unique
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

Methods without injector annotations are added to the target class:

```js
#mixin {targets: "com.example.TargetClass"}
zenClass TargetClassMixin {
    // Helper method WITH @Unique (RECOMMENDED to avoid conflicts)
    #mixin Unique
    function myUniqueHelper() as int {
        return this0.someField * 3;
    }

    #mixin ModifyReturnValue {method: "getValue", at: {value: "RETURN"}}
    function modifyValue(original as int) as int {
        return original + myUniqueHelper(); // Can call helper from injector, but also from outside
    }
}
```

Note that to make an added method static, you need to add `#mixin Static`.

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
import dynamic.zenutils.config.Mymodpack; // Generated from config name
import mods.zenutils.EventPriority;

function update() as void {
    native.noppes.vc.items.ItemMusket.zenutils_cfg_val = Mymodpack.weapons.musketLoadingTicks;
    // Repeat for all configurable mixins
}

events.register(function(event as native.net.minecraftforge.fml.client.event.ConfigChangedEvent.OnConfigChangedEvent) {
    if(event.getModID() != "mymodpack") return;
    update();
}, EventPriority.normal(), false);

update(); // Initial sync on script load
```

Players can now edit values via in-game config GUI, and changes will update your mixin behavior.

## Further Resources

- ZenUtils Wiki: https://github.com/friendlyhj/ZenUtils/wiki/Mixin
- MixinExtras Documentation: https://github.com/LlamaLad7/MixinExtras/wiki
- Example mixins: See `zenutilsmixins.zs` and `zenutilsmixins_client.zs` in your scripts folder
- SRG mappings: `mcpdeobfuscator/mappings/` in this project
