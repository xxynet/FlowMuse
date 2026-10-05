import type { PresetDef } from '@/types/flow'
import { realisticPortrait } from '@/presets/realisticPortrait'
import { figurine } from '@/presets/figurine'
import { memePack } from '@/presets/memePack'
import { lineStickerPack } from '@/presets/lineStickerPack'
import { stickerCharacterSwap } from '@/presets/stickerCharacterSwap'
import { styleTransfer } from '@/presets/styleTransfer'
import { fourPanelComic } from '@/presets/fourPanelComic'

/** 玩法模板列表，展示在左侧边栏，点击即载入画布 */
export const presetList: PresetDef[] = [
  lineStickerPack, stickerCharacterSwap, styleTransfer, fourPanelComic,
  realisticPortrait, figurine, memePack,
]
