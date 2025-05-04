import { ScAddr, ScConstruction, ScLinkContent, ScLinkContentType, ScTemplate, ScType } from 'ts-sc-client';
import { client } from '@api/sc/client';

const keynodes = [
    { id: 'current_user', type: ScType.ConstNode },
    { id: 'nrel_google_access_token', type: ScType.NodeNonRole },
];

export const create_current_user = async (credsJson: string) => {
    try {

        const link = await generateLinkText(credsJson);
        const res = await client.resolveKeynodes(keynodes);

        const template = new ScTemplate();
        template.quintuple(
            res['current_user'],
            ScType.VarCommonArc,
            link,
            ScType.VarPermPosArc,
            res['nrel_google_access_token'],
        );

        const r = await client.generateByTemplate(template, {});
    } catch (error) {
        console.error('Ошибка в записи пользователя в БЗ:', error);
        throw error;
    }
};

const generateLinkText = async (creds: string) => {
    const constructionLink = new ScConstruction();
    constructionLink.generateLink(ScType.ConstNodeLink, new ScLinkContent(creds, ScLinkContentType.String));
    const resultLinkNode = await client.generateElements(constructionLink);
    if (resultLinkNode.length) {
        return resultLinkNode[0];
    }
    return new ScAddr(0);
};
