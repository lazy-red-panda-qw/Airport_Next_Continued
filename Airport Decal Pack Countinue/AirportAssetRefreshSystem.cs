using Game;
using Game.Prefabs;
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using UnityTime = UnityEngine.Time;

namespace Airport_Decal_Pack_Countinue
{
    /// <summary>
    /// EAI's legacy importer can mutate a cached RenderPrefab without notifying
    /// PrefabSystem. Refresh each available asset after EAI finishes importing.
    /// This does not clear EAI's cache or touch another pack's prefabs.
    /// The mitigation still needs a cold-launch test in the actual game.
    /// </summary>
    public partial class AirportAssetRefreshSystem : GameSystemBase
    {
        internal static string AssetFolder;
        private PrefabSystem m_Prefabs;
        private Func<bool> m_ImportersFinished;
        private List<PrefabID> m_Expected;
        private float m_NextProbe;
        private float m_Started;
        private float m_ImportersFinishedAt = -1f;

        protected override void OnCreate()
        {
            base.OnCreate();
            m_Prefabs = World.GetOrCreateSystemManaged<PrefabSystem>();
            // This EAI type is internal; confine reflection to its known public
            // status method. If its API changes, ordinary EAI loading continues.
            try
            {
                Type manager = typeof(ExtraAssetsImporter.EAI).Assembly.GetType(
                    "ExtraAssetsImporter.AssetImporter.AssetsImporterManager");
                MethodInfo method = manager?.GetMethod("AreImportersFinished",
                    BindingFlags.Public | BindingFlags.Static);
                if (method == null || method.ReturnType != typeof(bool)
                    || method.GetParameters().Length != 0)
                    throw new MissingMethodException("EAI importer status method is unavailable.");
                m_ImportersFinished = (Func<bool>)Delegate.CreateDelegate(typeof(Func<bool>), method);
            }
            catch (Exception ex)
            {
                Mod.Log.Warn("Airport prefab refresh disabled: " + ex.Message);
                Enabled = false;
            }
        }

        protected override void OnUpdate()
        {
            if (AssetFolder == null || UnityTime.realtimeSinceStartup < m_NextProbe) return;
            m_NextProbe = UnityTime.realtimeSinceStartup + 0.5f;
            try
            {
                if (m_Expected == null)
                {
                    if (File.Exists(Path.Combine(AssetFolder, "disable-prefab-refresh.txt")))
                    {
                        Enabled = false;
                        return;
                    }
                    m_Expected = new List<PrefabID>();
                    foreach (string line in File.ReadAllLines(Path.Combine(AssetFolder, "airport-prefabs.tsv")))
                    {
                        string[] fields = line.Split('\t');
                        if (fields.Length == 2 && fields[0] != nameof(SurfacePrefab))
                            m_Expected.Add(new PrefabID(fields[0], fields[1]));
                    }
                    m_Started = UnityTime.realtimeSinceStartup;
                }
                if (UnityTime.realtimeSinceStartup - m_Started > 600f)
                {
                    Mod.Log.Warn("Airport prefab refresh timed out. Check EAI importer settings and missing-asset errors.");
                    Enabled = false;
                    return;
                }
                if (!m_ImportersFinished())
                {
                    m_ImportersFinishedAt = -1f;
                    return;
                }
                // Allow registrations queued on the main thread to settle.
                // A missing asset must not block every successfully imported one.
                if (m_ImportersFinishedAt < 0f)
                    m_ImportersFinishedAt = UnityTime.realtimeSinceStartup;
                if (UnityTime.realtimeSinceStartup - m_ImportersFinishedAt < 2f) return;

                var parents = new List<PrefabBase>();
                var renders = new List<PrefabBase>();
                var missing = new List<string>();
                foreach (PrefabID id in m_Expected)
                {
                    if (!m_Prefabs.TryGetPrefab(id, out PrefabBase parent))
                    {
                        missing.Add(id.ToString());
                        continue;
                    }
                    if (!m_Prefabs.TryGetPrefab(new PrefabID(nameof(RenderPrefab), parent.name + "_RenderPrefab"), out PrefabBase render))
                    {
                        missing.Add(id + " (RenderPrefab missing)");
                        continue;
                    }
                    parents.Add(parent);
                    renders.Add(render);
                }
                int queued = 0;
                int failed = 0;
                for (int i = 0; i < parents.Count; i++)
                {
                    PrefabBase parent = parents[i];
                    try
                    {
                        m_Prefabs.UpdatePrefab(renders[i]);
                        m_Prefabs.UpdatePrefab(parent);
                        if (m_Prefabs.TryGetPrefab(new PrefabID(nameof(StaticObjectPrefab), parent.name + "_Placeholder"), out PrefabBase placeholder))
                            m_Prefabs.UpdatePrefab(placeholder);
                        queued++;
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        Mod.Log.Warn("Airport prefab refresh failed for " + parent.name + ": " + ex.Message);
                    }
                }
                foreach (string id in missing) Mod.Log.Warn("Airport asset missing after EAI import: " + id);
                Mod.Log.Info($"Airport prefab refresh queued once: {queued}/{m_Expected.Count} assets; {missing.Count} missing; {failed} refresh failures.");
                Enabled = false;
            }
            catch (Exception ex)
            {
                Mod.Log.Warn("Airport prefab refresh disabled; EAI assets remain loaded: " + ex.Message);
                Enabled = false;
            }
        }
    }
}
