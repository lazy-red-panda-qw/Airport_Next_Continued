// Executes the production refresh system with a small in-memory game facade.
// This checks scheduling/failure isolation; it cannot validate Unity rendering.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Airport_Decal_Pack_Countinue;
using Game.Prefabs;

internal static class Program
{
    private static int Main()
    {
        CheckMissingDoesNotBlock();
        CheckImporterWait();
        CheckRefreshExceptionIsolation();
        CheckMissingRender();
        Console.WriteLine("PASS: missing assets, importer wait, refresh exceptions, missing render; production refresh code executed.");
        return 0;
    }

    private static RefreshProbe Setup(string name, params string[] manifest)
    {
        string path = Path.GetFullPath(Path.Combine("artifacts", "refresh-harness", name));
        Directory.CreateDirectory(path);
        File.WriteAllLines(Path.Combine(path, "airport-prefabs.tsv"), manifest);
        AirportAssetRefreshSystem.AssetFolder = path;
        UnityEngine.Time.realtimeSinceStartup = 0;
        ExtraAssetsImporter.AssetImporter.AssetsImporterManager.Finished = true;
        Mod.Log.Messages.Clear();
        var probe = new RefreshProbe();
        probe.Create();
        return probe;
    }

    private static void Add(RefreshProbe probe, string name, bool render = true)
    {
        probe.World.Prefabs.Add(nameof(StaticObjectPrefab), new StaticObjectPrefab { name = name });
        if (render) probe.World.Prefabs.Add(nameof(RenderPrefab), new RenderPrefab { name = name + "_RenderPrefab" });
    }

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new Exception(message);
    }

    private static void CheckMissingDoesNotBlock()
    {
        var p = Setup("missing", "StaticObjectPrefab\tA", "StaticObjectPrefab\tMissing", "StaticObjectPrefab\tB", "SurfacePrefab\tIgnored");
        Add(p, "A"); Add(p, "B");
        p.World.Prefabs.Add(nameof(StaticObjectPrefab), new StaticObjectPrefab { name = "A_Placeholder" });
        p.Tick(0); p.Tick(2);
        Require(!p.Enabled && p.World.Prefabs.Updates.Count == 5, "A missing parent blocked available assets or placeholder refresh.");
        Require(Mod.Log.Messages.Any(x => x.Contains("2/3 assets; 1 missing; 0 refresh failures")), "Missing asset summary incorrect.");
        Require(Mod.Log.Messages.Any(x => x.Contains("StaticObjectPrefab:Missing")), "Missing asset name not logged.");
        p.Tick(4);
        Require(p.World.Prefabs.Updates.Count == 5, "Refresh ran more than once.");
    }

    private static void CheckImporterWait()
    {
        var p = Setup("wait", "StaticObjectPrefab\tA"); Add(p, "A");
        ExtraAssetsImporter.AssetImporter.AssetsImporterManager.Finished = false;
        p.Tick(0); p.Tick(2);
        Require(p.World.Prefabs.Updates.Count == 0, "Refreshed before importer completion.");
        ExtraAssetsImporter.AssetImporter.AssetsImporterManager.Finished = true;
        p.Tick(3); p.Tick(4);
        Require(p.World.Prefabs.Updates.Count == 0, "Registration settling delay was skipped.");
        p.Tick(5);
        Require(!p.Enabled && p.World.Prefabs.Updates.Count == 2, "Completed importer never refreshed.");
    }

    private static void CheckRefreshExceptionIsolation()
    {
        var p = Setup("exception", "StaticObjectPrefab\tA", "StaticObjectPrefab\tB"); Add(p, "A"); Add(p, "B");
        p.World.Prefabs.Failures.Add("A_RenderPrefab");
        p.Tick(0); p.Tick(2);
        Require(!p.Enabled && p.World.Prefabs.Updates.Contains("B"), "An exception blocked later assets.");
        Require(Mod.Log.Messages.Any(x => x.Contains("1/2 assets; 0 missing; 1 refresh failures")), "Exception summary incorrect.");
    }

    private static void CheckMissingRender()
    {
        var p = Setup("render", "StaticObjectPrefab\tA", "StaticObjectPrefab\tB"); Add(p, "A", false); Add(p, "B");
        p.Tick(0); p.Tick(2);
        Require(!p.Enabled && p.World.Prefabs.Updates.Contains("B"), "Missing render blocked later assets.");
        Require(Mod.Log.Messages.Any(x => x.Contains("RenderPrefab missing")), "Missing render not diagnosed.");
    }
}

internal sealed class RefreshProbe : AirportAssetRefreshSystem
{
    public void Create() => base.OnCreate();
    public void Tick(float time)
    {
        UnityEngine.Time.realtimeSinceStartup = time;
        if (Enabled) base.OnUpdate();
    }
}

namespace Airport_Decal_Pack_Countinue
{
    internal static class Mod { public static TestLog Log = new TestLog(); }
    internal sealed class TestLog
    {
        public readonly List<string> Messages = new List<string>();
        public void Info(string text) => Messages.Add(text);
        public void Warn(string text) => Messages.Add(text);
    }
}
namespace Game
{
    public abstract class GameSystemBase
    {
        public bool Enabled = true;
        public TestWorld World = new TestWorld();
        protected virtual void OnCreate() { }
        protected virtual void OnUpdate() { }
    }
    public sealed class TestWorld
    {
        public readonly PrefabSystem Prefabs = new PrefabSystem();
        public T GetOrCreateSystemManaged<T>() where T : class => Prefabs as T;
    }
}
namespace Game.Prefabs
{
    public class PrefabBase { public string name; }
    public sealed class RenderPrefab : PrefabBase { }
    public sealed class StaticObjectPrefab : PrefabBase { }
    public sealed class SurfacePrefab : PrefabBase { }
    public readonly struct PrefabID
    {
        private readonly string type, name;
        public PrefabID(string type, string name) { this.type = type; this.name = name; }
        public override string ToString() => type + ":" + name;
    }
    public sealed class PrefabSystem
    {
        private readonly Dictionary<string, PrefabBase> prefabs = new Dictionary<string, PrefabBase>();
        public readonly List<string> Updates = new List<string>();
        public readonly HashSet<string> Failures = new HashSet<string>();
        public void Add(string type, PrefabBase prefab) => prefabs[new PrefabID(type, prefab.name).ToString()] = prefab;
        public bool TryGetPrefab(PrefabID id, out PrefabBase prefab) => prefabs.TryGetValue(id.ToString(), out prefab);
        public void UpdatePrefab(PrefabBase prefab)
        {
            if (Failures.Contains(prefab.name)) throw new InvalidOperationException("Injected refresh failure.");
            Updates.Add(prefab.name);
        }
    }
}
namespace UnityEngine { public static class Time { public static float realtimeSinceStartup; } }
namespace ExtraAssetsImporter { public static class EAI { } }
namespace ExtraAssetsImporter.AssetImporter
{
    internal static class AssetsImporterManager
    {
        public static bool Finished;
        public static bool AreImportersFinished() => Finished;
    }
}
