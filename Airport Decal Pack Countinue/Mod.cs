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
            Log.Info("Airport Details Pack 0.6.7: EAI import requested for airport markings, flexible apron bases and independent details.");
        }

        public void OnDispose()
        {
        }
    }
}
