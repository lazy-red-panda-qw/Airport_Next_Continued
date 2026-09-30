using Colossal.Logging;
using Game;
using Game.Modding;
using Game.SceneFlow;
using System.IO;

namespace Airport_Decal_Pack_Countinue
{
    public class Mod : IMod
    {

        internal static readonly ILog Log = LogManager.GetLogger(nameof(Airport_Decal_Pack_Countinue))
            .SetShowsErrorsInUI(false);

        public void OnLoad(UpdateSystem updateSystem)
        {
            if (!GameManager.instance.modManager.TryGetExecutableAsset(this, out var asset)) return;

            string pathToModFolder = new FileInfo(asset.path).DirectoryName;

            ExtraAssetsImporter.EAI.LoadCustomAssets(pathToModFolder);
            // The deployment target flattens the source CustomAssets directory.
            // EAI and the generated manifest are both rooted beside this DLL.
            AirportAssetRefreshSystem.AssetFolder = pathToModFolder;
            updateSystem.UpdateAt<AirportAssetRefreshSystem>(SystemUpdatePhase.MainLoop);
            Log.Info("Airport Details Pack 0.6.0: ICAO asset configurations registered.");
        }

        public void OnDispose()
        {
            AirportAssetRefreshSystem.AssetFolder = null;
        }
    }
}
